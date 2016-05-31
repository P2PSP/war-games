#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, getopt, shutil
import time
import random
import shlex, subprocess
import re
import glob
import platform
from color import Color

processes = []

DEVNULL = open(os.devnull, 'wb')
SEED = 12345678

nPeers = nTrusted = nMalicious = sizeTeam = nPeersTeam = 0

port = 60000
playerPort = 61000

currentRound = 0

LAST_ROUND_NUMBER = 0

INIT_TIME = 0
TOTAL_TIME = 60

trusted_peers = []
mp_expelled_by_tps = []
angry_peers = []
angry_peers_retired = []
buffer_values = {}

P_IN = 50
P_OUT = 50
P_WIP = 50
P_MP = 100 - P_WIP
P_MPL = 60
MPTR = 5
BFR_min = 0.5
alpha = 0.9

#TODO: Churn point 5. Weibull distribution.

def checkdir():
    if not os.path.exists("./strpe-testing"):
        os.mkdir("./strpe-testing")

def usage():
    print "args error"

def run(runStr, out = DEVNULL, alias = "", ttl = None, entityType = ""):
    proc = subprocess.Popen(shlex.split(runStr), stdout=out, stderr=out)
    processes.append((proc, alias, ttl, entityType))
    return proc
            

def killall():
    for proc in processes:
        if proc[0].poll() == None:
            proc[0].kill()

def runStream():
    if platform.system() == "Linux":
        run("cvlc Big_Buck_Bunny_small.ogv --sout \"#duplicate{dst=standard{mux=ogg,dst=:8080/test.ogg,access=http}}\"")
    else:
        run("/Applications/VLC.app/Contents/MacOS/VLC Big_Buck_Bunny_small.ogv --sout \"#duplicate{dst=standard{mux=ogg,dst=,access=http}}\"")
    time.sleep(0.5)

def runSplitter(ds = False):
    prefix = ""
    if ds: prefix = "ds"
    run("./splitter.py --port 8001 --source_port 8080 --max_chunk_loss 16 --strpeds_log strpe-testing/splitter.log --p_mpl "+str(P_MPL), open("strpe-testing/splitter.out", "w"))

    time.sleep(0.25)

def runPeer(trusted = False, malicious = False, ds = False):
    global port, playerPort, TOTAL_TIME, DEVNULL, MPTR
    #run peer
    runStr = "./peer.py --splitter_port 8001 --use_localhost --port {0} --player_port {1}".format(port, playerPort)

    peertype = "WIP"
    if trusted:
        peertype = "TP"
    if malicious:
        peertype = "MP"
        runStr += " --malicious --persistent --mptr {0}".format(MPTR)
    if not malicious:
         runStr += " --strpeds_log ./strpe-testing/peer{0}.log".format(port)

    run(runStr, open("./strpe-testing/peer{0}.out".format(port), "w"), "127.0.0.1:"+str(port))
    time.sleep(0.25)

    #Weibull distribution in this random number:
    ttl = random.randint(TOTAL_TIME-(TOTAL_TIME/8),TOTAL_TIME+(TOTAL_TIME/4))
    alias = "127.0.0.1:"+str(port)

    #run netcat
    proc = run("nc 127.0.0.1 {0}".format(playerPort), DEVNULL, alias, ttl, peertype)
                         
    port, playerPort = port + 1, playerPort + 1

   

def check(x):
    with open("./strpe-testing/splitter.log") as fh:
        for line in fh:
            pass
        result = re.match("(\d*.\d*)\t(\d*)\s(\d*).*", line)
        if result != None and int(result.group(3)) <= x:
            return True
    return False

def initializeTeam(nPeers, nInitialTrusted):

    print "running stream"
    runStream()

    print "running splitter"
    runSplitter(True)

    # clear the trusted.txt file
    with open("trusted.txt", "w"):
        pass
    # clear the attacked.txt file
    with open("attacked.txt", "w"):
        pass

    with open("malicious.txt", "w"):
        pass

    with open("regular.txt", "w"):
        pass

    print "running peers"

    for _ in range(nInitialTrusted):
        print Color.green, "In: <--", Color.none, "TP 127.0.0.1:{0}".format(port)
        with open("trusted.txt", "a") as fh:
            fh.write('127.0.0.1:{0}\n'.format(port))
            fh.close()
        trusted_peers.append('127.0.0.1:{0}'.format(port))
        runPeer(True, False, True)

    for _ in range(nPeers):
       print Color.green, "In: <--", Color.none, "WIP 127.0.0.1:{0}".format(port)
       runPeer(False, False, True)

def churn():
    global trusted_peers, P_IN, nTrusted, nPeersTeam, INIT_TIME, nMalicious, TOTAL_TIME, processes

    #while checkForRounds():
    while TOTAL_TIME > (time.time()-INIT_TIME):
        r = random.randint(1,100)
        if r <= P_IN:
            addRegularOrMaliciousPeer()

        r = random.randint(1,100)    
        if r <= P_IN and nTrusted>0:
            print Color.green, "In: <--", Color.none, "TP 127.0.0.1:{0}".format(port)
            with open("trusted.txt", "a") as fh:
                fh.write('127.0.0.1:{0}\n'.format(port))
                fh.close()
            trusted_peers.append('127.0.0.1:{0}'.format(port))
            nTrusted-=1
            nPeersTeam+=1
            runPeer(True, False, True)


        checkForBufferTimes()

        anyMPexpelled = checkForMaliciousExpelled()
        if anyMPexpelled != None:
            print Color.red, "Out: --> MP", anyMPexpelled, Color.none
            nMalicious+=1
	    nPeersTeam-=1

        for p in processes:
            if p[2] != None and p[2] <= (time.time()-INIT_TIME):
                if p[0].poll() == None:
                    if (p[1] not in mp_expelled_by_tps):
                        print Color.red, "Out:-->", Color.none, p[3], p[1]
                        p[0].kill()

                        if p[3] == "TP":
                            nTrusted+=1

                        if p[3] == "MP":
                            nMalicious+=1
                    
                        nPeersTeam-=1

            if (p[1] in angry_peers):
                if p[1] not in angry_peers_retired:
                    print Color.red, "Out: --> ",p[3], p[1], "(by BFR_min)", Color.none
                
                    p[0].kill()

                    angry_peers_retired.append(p[1])
                 
                    if p[3] == "TP":
                        nTrusted+=1

                    if p[3] == "MP":
                        nMalicious+=1
                            
                    nPeersTeam-=1
        
        #print "Timer: "+ str(TIMER)
        #time.sleep(0.5)


def checkForBufferTimes():
    global BFR_min, angry_peers, buffer_values
    fileList = glob.glob("./strpe-testing/peer*.log")
    for f in fileList:
        
        regex_peer = re.compile("./strpe-testing/peer(\d*).log")
        result = regex_peer.match(f)
        if result != None:
            peer_str = "127.0.0.1:"+str(int(result.group(1)))
                
        if peer_str not in buffer_values:
            buffer_values[peer_str] = 1

        buffer_filling = getLastBufferFor(f)
        if buffer_filling != None: 
            BF = (buffer_filling/0.5)
            buffer_values[peer_str] = alpha * BF + (1-alpha) * buffer_values[peer_str]
        
        if (buffer_values[peer_str] != 0) and (buffer_values[peer_str] < BFR_min):
            if peer_str not in angry_peers:
                angry_peers.append(peer_str)
    
def getLastBufferFor(inFile):
    if os.path.getsize(inFile) == 0:
        return None
    
    regex_filling = re.compile("(\d*.\d*)\tbuffer\sfilling\s(\d*.\d*)")
    filling = 0.5
    with open(inFile) as f:
        for line in f:
            pass
        
    result = regex_filling.match(line)
    if result != None:
        filling = float(result.group(2))

    return filling

def addRegularOrMaliciousPeer():
    global nMalicious, nPeersTeam, P_MP, P_WIP, iteration, nTrusted, TOTAL_TIME, currentRound
    if sizeTeam > nPeersTeam:
        r = random.randint(1,100)
        if r <= P_MP:
            if nMalicious>0:
                with open("malicious.txt", "a") as fh:
                    fh.write('127.0.0.1:{0}\n'.format(port))
                    fh.close()
                print Color.green, "In: <--", Color.none, "MP 127.0.0.1:{0}".format(port)
	        nMalicious-=1
	        nPeersTeam+=1
                runPeer(False, True, True)
        else:
            #with open("regular.txt", "a") as fh:
            #    fh.write('127.0.0.1:{0}\n'.format(port))
            #    fh.close()
            print Color.green, "In: <--", Color.none, "WIP 127.0.0.1:{0}".format(port)
	    nPeersTeam+=1
            runPeer(False, False, True)

    currentRound = findLastRound()
    progress ="Round "+ str(currentRound-LAST_ROUND_NUMBER)+" Size "+str(sizeTeam)+"/"+str(nPeersTeam)
    sys.stdout.flush()
    print progress,
    print str(int(time.time()-INIT_TIME))+"/"+str(TOTAL_TIME),
    #print "#"*(iteration%5),
    print '\r',

def checkForTrusted():
    with open("./strpe-testing/splitter.log") as fh:
        for line in fh:
            pass
        result = re.match("(\d*.\d*)\t(\d*)\s(\d*)\s(.*)", line)

        if result != None:
            peers = result.group(4)
            tCnt = 0
            for peer in peers.split(' '):
                if peer in trusted_peers:
                    tCnt += 1

            return tCnt == nTrusted

    return True

def checkForMaliciousExpelled():
    global mp_expelled_by_tps
    with open("./strpe-testing/splitter.log") as fh:
        for line in fh:
            result = re.match("(\d*)\tbad peer ([0-9]+(?:\.[0-9]+){3}:[0-9]+)\((.*?)\)", line)
            if result != None and result.group(2) not in mp_expelled_by_tps:
                mp_expelled_by_tps.append(result.group(2))
                return result.group(2) +" ("+ result.group(3)+")"
    return None

def saveLastRound():
    global LAST_ROUND_NUMBER, INIT_TIME
    LAST_ROUND_NUMBER = findLastRound()
    INIT_TIME = time.time()

def findLastRound():
    global iteration
    with open("./strpe-testing/splitter.log") as fh:
        for line in fh:
            pass
        result = re.match("(\d*.\d*)\t(\d*)\s(\d*).*", line)
        if result != None:
             return int(result.group(2))
    return -1

#def checkForRounds():
#    global currentRound
#    lastRound = findLastRound()
#    if lastRound != currentRound:
#        currentRound = lastRound
#    return currentRound - LAST_ROUND_NUMBER < Q

def main(args):
    random.seed(SEED)

    try:
        opts, args = getopt.getopt(args, "n:t:i:m:z:s:d:c")
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    ds = False
    global nPeers, nTrusted, nMalicious, sizeTeam, nPeersTeam, TOTAL_TIME
    nPeers = 2
    nTrusted = nInitialTrusted = 1
    nMalicious = 0
    sizeTeam= nPeersTeam = 2
    for opt, arg in opts:
        if opt == "-n":
            nPeers = int(arg)
        elif opt == "-t":
            nTrusted = int(arg)
        elif opt == "-i":
            nInitialTrusted = int(arg)
        elif opt == "-m":
            nMalicious = int(arg)
        elif opt == "-z":
	    sizeTeam = int(arg)
        elif opt == "-s":
            ds = True
        elif opt == "-d":
            TOTAL_TIME = int(arg)
        elif opt == "-c":
            try:
                os.remove("trusted.txt")
                os.remove("malicious.txt")
                os.remove("attacked.txt")
                os.remove("regular.txt")
                shutil.rmtree("./strpe-testing")
            except:
                pass
            
            print("temp files removed")
            sys.exit()

    print 'running initial team with {0} peers ({1} trusted)'.format(nPeers, nInitialTrusted)

    nPeers = nPeers - nInitialTrusted #- nMalicious # for more friendly user input
    nPeersTeam = nPeers + nInitialTrusted
    nTrusted = nTrusted - nInitialTrusted
    checkdir()
    
    initializeTeam(nPeers, nInitialTrusted)

    print "Team Initialized"
    
    for i in xrange(10,0,-1):
        print "Wait for buffering",
        print str(i)+'  \r',
        sys.stdout.flush()
        time.sleep(1)
        
    
    #time.sleep(10) # time for all peers buffering
    saveLastRound()
    print "LAST_ROUND_NUMBER", LAST_ROUND_NUMBER

    print "----- Simulating Churn -----"
    churn()

    print "******************* End of Simulation *******************"
    currentRound = findLastRound()
    print "Rounds= " + str(currentRound-LAST_ROUND_NUMBER) + " TIME= " + str(TOTAL_TIME) + " LRN= " + str(LAST_ROUND_NUMBER)

    killall()

    print "******************* Parsing Results  ********************"
    path = "./strpe-testing/sample.dat"
    print "Target file: "+path
    #process = run("./parse.py -r "+str(LAST_ROUND_NUMBER), open(path,"w"))
    #Initial round is not necessary because log is recorded after buffering.
    process = run("./parse.py", open(path,"w"))
    process.wait()
    print "Done!"

    print "******************* Plotting Results  *******************"
    run("gnuplot -e \"filename='"+path+"'\" plot_team.gp")
    run("gnuplot -e \"filename='"+path+"'\" plot_buffer.gp")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        killall()
