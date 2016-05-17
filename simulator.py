#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, getopt, shutil
import time
import random
import shlex, subprocess
import re
import platform

processes = []
DEVNULL = open(os.devnull, 'wb')
SEED = 12345678

nPeers = nTrusted = nMalicious = sizeTeam = nPeersTeam = 0

port = 60000
playerPort = 61000

currentRound = 0
iteration=0

LAST_ROUND_NUMBER = 0
Q = 500

trusted_peers = []

P_IN = 100
P_OUT = 100
P_WIP = 50
P_MP = 100 - P_WIP

#TODO: Churn point 5. Weibull distribution.
#TODO: MP point 2. MP should not attack over 50% of the team.
#TODO: WIP behaviour under attacks.

def checkdir():
    if not os.path.exists("./strpe-testing"):
        os.mkdir("./strpe-testing")

def usage():
    print "args error"

def run(runStr, out = DEVNULL):
    proc = subprocess.Popen(shlex.split(runStr), stdout=out, stderr=out)
    processes.append(proc)

def killall():
    for proc in processes:
        proc.kill()

def runStream():
    if platform.system() == "Linux":
        run("vlc Big_Buck_Bunny_small.ogv --sout \"#duplicate{dst=standard{mux=ogg,dst=:8080/test.ogg,access=http}}\"")
    else:
        run("/Applications/VLC.app/Contents/MacOS/VLC Big_Buck_Bunny_small.ogv --sout \"#duplicate{dst=standard{mux=ogg,dst=,access=http}}\"")
    time.sleep(2)

def runSplitter(ds = False):
    prefix = ""
    if ds: prefix = "ds"
    run("./splitter.py --port 8001 --source_port 8080 --strpeds_log strpe-testing/splitter.log".format(prefix), open("strpe-testing/splitter.out", "w"))

    time.sleep(0.25)

def runPeer(trusted = False, malicious = False, ds = False):
    global port
    global playerPort
    #run peer
    #strpeds = ""
    #if ds: strpeds = "--strpeds"
    runStr = "./peer.py --splitter_port 8001 --use_localhost --port {0} --player_port {1}".format(port, playerPort)
    #if trusted:
        #runStr += " --trusted"
    if malicious:
        runStr += " --malicious --persistent"
    if not malicious:
         runStr += " --strpeds_log ./strpe-testing/peer{0}.log".format(port)
    run(runStr, open("strpe-testing/peer{0}.out".format(port), "w"))
    time.sleep(0.5)
    #run netcat
    run("nc 127.0.0.1 {0}".format(playerPort))
    port, playerPort = port + 1, playerPort + 1

def check(x):
    with open("./strpe-testing/splitter.log") as fh:
        for line in fh:
            pass
        result = re.match("(\d*.\d*)\t(\d*)\s(\d*).*", line)
        if result != None and int(result.group(3)) <= x:
            return True
    return False

def initializeTeam(nPeers, nTrusted):
    global trusted_peers

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

    for _ in range(nTrusted):
        print "TP 127.0.0.1:{0}".format(port)
        with open("trusted.txt", "a") as fh:
            fh.write('127.0.0.1:{0}\n'.format(port))
            fh.close()
        trusted_peers.append('127.0.0.1:{0}'.format(port))
        runPeer(True, False, True)


    for _ in range(nPeers):
        print "WIP 127.0.0.1:{0}".format(port)
        runPeer(False, False, True)

def churn():
    global trusted_peers

    while checkForRounds():
        addRegularOrMaliciousPeer()
        if not checkForTrusted():
            print "TP 127.0.0.1:{0}".format(port)
            with open("trusted.txt", "a") as fh:
                fh.write('127.0.0.1:{0}\n'.format(port))
                fh.close()
            trusted_peers.append('127.0.0.1:{0}'.format(port))
            runPeer(True, False, True)
        time.sleep(0.5)

def addRegularOrMaliciousPeer():
    global nMalicious, nPeersTeam, P_MP, P_WIP, iteration
    if sizeTeam > nPeersTeam:
        r = random.randint(1,100)
        if r <= P_MP:
            if nMalicious>0:
                with open("malicious.txt", "a") as fh:
                    fh.write('127.0.0.1:{0}\n'.format(port))
                    fh.close()
                    print "MP 127.0.0.1:{0}".format(port)
	            nMalicious-=1
	            nPeersTeam+=1
                    runPeer(False, True, True)
        else:
            with open("regular.txt", "a") as fh:
                fh.write('127.0.0.1:{0}\n'.format(port))
                fh.close()
            print "WIP 127.0.0.1:{0}".format(port)
	    nPeersTeam+=1
            runPeer(False, False, True)
    else:
	progress ="Round "+ str(currentRound-LAST_ROUND_NUMBER)+"/"+str(Q)+" Size "+str(sizeTeam)+"/"+str(nPeersTeam)
        iteration += 1
        sys.stdout.flush()
        print progress,
        print "#"*(iteration%5),
        print '\r'*(len(progress)+iteration),

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


def saveLastRound():
    global LAST_ROUND_NUMBER
    LAST_ROUND_NUMBER = findLastRound()

def findLastRound():
    global iteration
    with open("./strpe-testing/splitter.log") as fh:
        for line in fh:
            pass
        result = re.match("(\d*.\d*)\t(\d*)\s(\d*).*", line)
        if result != None:
             return int(result.group(2))
    return -1

def checkForRounds():
    global currentRound, iteration
    lastRound = findLastRound()
    if lastRound != currentRound:
        currentRound = lastRound
        iteration = 0
    return currentRound - LAST_ROUND_NUMBER < Q

def main(args):
    random.seed(SEED)

    try:
        opts, args = getopt.getopt(args, "n:t:m:z:s:c")
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    ds = False
    global nPeers, nTrusted, nMalicious, sizeTeam, nPeersTeam
    nPeers = 10
    nTrusted = 1
    nMalicious = 0
    sizeTeam= nPeersTeam = 10
    for opt, arg in opts:
        if opt == "-n":
            nPeers = int(arg)
        elif opt == "-t":
            nTrusted = int(arg)
        elif opt == "-m":
            nMalicious = int(arg)
        elif opt == "-z":
	    sizeTeam = int(arg)
        elif opt == "-s":
            ds = True
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

    print 'running with {0} peers ({1} trusted and {2} mal)'.format(nPeers, nTrusted, nMalicious)

    nPeers = nPeers - nTrusted #- nMalicious # for more friendly user input
    nPeersTeam = nPeers + nTrusted
    checkdir()

    initializeTeam(nPeers, nTrusted)

    time.sleep(10) # time for all peers buffering
    saveLastRound()
    print "LAST_ROUND_NUMBER", LAST_ROUND_NUMBER

    print "simulating churn"
    churn()

    #time.sleep(60)
    print "******************* finish! *******************"

    killall()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        killall()
