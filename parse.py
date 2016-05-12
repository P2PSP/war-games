#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, getopt
import re
import glob

max_buffer_correctness = 0
min_buffer_correctness = 1
max_buffer_filling = 0
min_buffer_filling = 1

def usage():
    print ""
    return

def calcAverageBufferCorrectnes(roundTime):
    fileList = glob.glob("./strpe-testing/peer*.log")
    correctnesSum = fillingSum = 0.0
    NN = 0
    for f in fileList:
        info = calcAverageInFile(f, roundTime)
        if (info[0] != None):
            correctnesSum += info[0]
            fillingSum += info[1]
            NN += 1
    return (correctnesSum / NN, fillingSum / NN)

def calcAverageInFile(inFile, roundTime):
    regex_correctness = re.compile("(\d*.\d*)\tbuffer\scorrectnes\s(\d*.\d*)")
    regex_filling = re.compile("(\d*.\d*)\tbuffer\sfilling\s(\d*.\d*)")
    correctness = -1.0
    filling = -1.0
    with open(inFile) as f:
        for line in f:
            result = regex_correctness.match(line)
            result2 = regex_filling.match(line)
            if result != None and correctness == -1.0:
                ts = float(result.group(1))
                if ts >= roundTime:
                    correctness = float(result.group(2))
            if result2 != None and filling == -1.0:
                ts = float(result2.group(1))
                if ts >= roundTime:
                    filling = float(result2.group(2))
            if correctness != -1.0 and filling != -1.0:
                return (correctness, filling)

    return (None, None)

def main(args):
    inFile = ""
    nPeers = nMalicious = lastRound = 0
    try:
        opts, args = getopt.getopt(args, "r:")
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-r":
            lastRound = int(arg)

    regex = re.compile("(\d*.\d*)\t(\d*)\s(\d*)\s(.*)")
    startParse = False
    roundOffset = 0
    print "round\t#WIPs\t#MPs\t#TPs\tteamsize\tcorrectness\tfilling"
    with open("./strpe-testing/splitter.log") as f:
        for line in f:
            result = regex.match(line)
            if result != None:
                ts = float(result.group(1))
                currentRound = int(result.group(2))
                currentTeamSize = int(result.group(3))
                peers = result.group(4).split(' ')
                trusted = 0
                malicious = 0

                with open("trusted.txt", "r") as fh:
                    for line in fh:
                        if line[:-1] in peers:
                            trusted += 1
                with open("malicious.txt", "r") as fh:
                    for line in fh:
                        if line[:-1] in peers:
                            malicious += 1

                if currentRound >= lastRound and not startParse:
                    startParse = True
                    roundOffset = currentRound
                if startParse:
                    info = calcAverageBufferCorrectnes(ts)
                    print "{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}".format(currentRound - roundOffset + 1, len(peers) - malicious - trusted, malicious, trusted, currentTeamSize, info[0], info[1])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
