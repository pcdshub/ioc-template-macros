#!/usr/bin/env python
import os
import sys
import re
import string

def read_config(file):
    d = {}
    i = {}
    d["DIRNAME"] = os.getcwd().split('/')[-1]
    try:
        fp = open(file)
    except:
        fp = open("../" + file)
    lines = fp.readlines()
    fp.close()
    eq      = re.compile("^([A-Za-z0-9_]*)=(.*)$")
    eqq     = re.compile('^([A-Za-z0-9_]*)="(.*)"$')
    eqqq    = re.compile("^([A-Za-z0-9_]*)='(.*)'$")
    inst    = re.compile("^([A-Za-z0-9_]*)\((.*)\)$")

    prminst = re.compile("^([A-Za-z_]*)([0-9_]*)(,)")
    prmeq   = re.compile("^([A-Za-z0-9_]*)=([^,]*)(,)")
    prmeqq  = re.compile('^([A-Za-z0-9_]*)="([^"]*)"(,)')
    prmeqqq = re.compile("^([A-Za-z0-9_]*)='([^']*)'(,)")
    for l in lines:
        l = l.strip()
        m = inst.search(l)
        if m != None:
            iname = m.group(1)
            params = m.group(2) + ","
            try:
                allinst = i[iname]
            except:
                allinst = []
                i[iname] = []
            # We've found an instantiation.  Create a local dictionary, dd, for its
            # names, and also add the full names to the main dictionary.
            dd = {}
            n = str(len(allinst))
            dd["INDEX"] = n
            while (params != ""):
                m = prmeqqq.search(params)
                if m == None:
                    m = prmeqq.search(params)
                    if m == None:
                        m = prmeq.search(params)
                if m != None:
                    # Parameter of the form VAR=VAL. Global dictionary will also
                    # get inameVARn=VAL.
                    var = m.group(1)
                    val = m.group(2)
                    dd[var] = val
                    d[iname + var + n] = val
                    params = params[m.end(3):len(params)]
                else:
                    m = prminst.search(params)
                    if m != None:
                        # Parameter of the form INSTn.  Find the instance, and
                        # add all of its named parameters VAL with the name
                        # INSTVAL.
                        useinst = m.group(1)
                        usenum = int(m.group(2))
                        used = i[useinst][usenum]
                        for k in used.keys():
                            var = useinst + k
                            val = used[k]
                            dd[var] = val
                        params = params[m.end(3):len(params)]
                    else:
                        print "Unknown parameter in line %s" % params
                        params = ""
            i[iname].append(dd)
            continue
        m = eqqq.search(l)
        if m == None:
            m = eqq.search(l)
            if m == None:
                m = eq.search(l)
        if m != None:
            var = m.group(1)
            val = m.group(2)
            d[var] = val;
            continue
        if l != "" and l[0] != '#':
            print "Skipping unknown line: %s" % l
    return (d, i)

def expand(ddict, idict, lines, f):
    i = 0
    lp = re.compile("^\$\$LOOP\((.*)\)$")
    dd = re.compile("^(.*?)\$\$")
    tr = re.compile('^TRANSLATE\((.*?),"(.*?)","(.*?)"\)')
    paren = re.compile("^\((.*?)\)")
    word = re.compile("^([A-Za-z0-9_]*)")
    while i < len(lines):
        if (lines[i] == ""):
            # Blank line!
            f.write("\n");
            i += 1
            continue
        m = lp.search(lines[i])
        if m != None:
            # $$LOOP(module) directive
            iname = m.group(1)
            j = i + 1
            while lines[j] != lines[i] and j < len(lines):
                j += 1
            if j == len(lines):
                print "Error, can't find closing %s" % lines[i]
                return
            try:
                ilist = idict[iname]
            except:
                ilist = []
            for inst in ilist:
                ddnew = ddict.copy()
                ddnew.update(inst)
                expand(ddnew, idict, lines[i+1:j], f)
            i = j + 1
            continue
        m = dd.search(lines[i])
        if m == None:
            # Line without a $$.
            f.write("%s\n" % lines[i])
            i += 1
            continue
        f.write(m.group(1))
        lines[i] = lines[i][m.end(1)+2:len(lines[i])]
        if lines[i][0:10] == "TRANSLATE(":
            m = tr.search(lines[i])
            if m != None:
                try:
                    val = ddict[m.group(1)].translate(string.maketrans(m.group(2), m.group(3)))
                    f.write(val)
                except:
                    pass
                lines[i] = lines[i][m.end(3)+2: len(lines[i])]
            else:
                print "Malformed $$TRANSLATE?"
        else:
            if lines[i][0] == "(":
                m = paren.search(lines[i])
            else:
                m = word.search(lines[i])
            if m != None:
                try:
                    val = ddict[m.group(1)]
                    f.write(val)
                except:
                    pass
                if lines[i][0] == '(':
                    lines[i] = lines[i][m.end(1)+1: len(lines[i])]
                else:
                    lines[i] = lines[i][m.end(1): len(lines[i])]
            else:
                print "Can't find word?!?"

if __name__ == '__main__':
    av = sys.argv;
    if len(av) < 3:
        print "Usage: expand.py TEMPLATE OUTFILE"
        sys.exit(1)
    config=read_config("config")
    lines=open(sys.argv[1]).readlines()
    lines=[l.strip() for l in lines]
    fp = open(sys.argv[2], 'w')
    expand(config[0], config[1], lines, fp)
    sys.exit(0)
