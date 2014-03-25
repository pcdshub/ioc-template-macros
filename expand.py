#!/usr/bin/env python
import os
import sys
import re
import string
import ast
import operator
import StringIO

expand_path = []

def myopen(file):
    try:
        fp = open(file)
        return fp
    except:
        pass
    if file[0] == '/':
        return None
    for f in expand_path:
        fn = f + "/" + file
        try:
            fp = open(fn)
            return fp
        except:
            pass
    return None

class config():
    def __init__(self):
        self.dirname = os.getcwd().split('/')[-1]
        self.ddict = {}
        self.idict = {}

        # Pre-define some regular expressions!
        self.doubledollar = re.compile("^(.*?)\$\$")
        self.keyword      = re.compile("^(LOOP|IF|INCLUDE|TRANSLATE|COUNT)\(|^(CALC)\{")
        self.parens       = re.compile("^\(([^)]*?)\)")
        self.brackets     = re.compile("^\{([^}]*?)\}")
        self.trargs       = re.compile('^\(([^,]*?),"([^"]*?)","([^"]*?)"\)')
        self.ifargs       = re.compile('^\(([^,)]*?),([^,)]*?),([^,)]*?)\)')
        self.word         = re.compile("^([A-Za-z0-9_]*)")
        self.operators = {ast.Add: operator.add,
                          ast.Sub: operator.sub,
                          ast.Mult: operator.mul,
                          ast.Div: operator.truediv,
                          ast.Pow: operator.pow,
                          ast.LShift : operator.lshift,
                          ast.RShift: operator.rshift,
                          ast.BitOr: operator.or_,
                          ast.BitAnd : operator.and_,
                          ast.BitXor: operator.xor}

    def create_instance(self, iname, id, idict, ndict):
        try:
            allinst = idict[iname]
        except:
            allinst = []
            idict[iname] = []
        n = str(len(allinst))
        if id != None:
            ndict[id] = (iname, int(n))
        dd = {}
        dd["INDEX"] = n
        return (dd, n)

    def finish_instance(self, iname, idict, dd):
        idict[iname].append(dd)

    def read_config(self, file, extra):
        w       = re.compile("^[ \t]*([^ \t=]+)")
        wq      = re.compile('^[ \t]*"([^"]*)"')
        wqq     = re.compile("^[ \t]*'([^']*)'")
        assign  = re.compile("^[ \t]*=")
        sp      = re.compile("^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]+(.+?)[ \t]*$")
        spq     = re.compile('^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]+"([^"]*)"[ \t]*$')
        spqq    = re.compile("^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]+'([^']*)'[ \t]*$")
        eq      = re.compile("^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*?)[ \t]*$")
        eqq     = re.compile('^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*"([^"]*)"[ \t]*$')
        eqqq    = re.compile("^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*'([^']*)'[ \t]*$")
        inst    = re.compile("^[ \t]*(([A-Za-z_][A-Za-z0-9_]*):[ \t]*)?([A-Za-z_][A-Za-z0-9_]*)\((.*)\)[ \t]*$")
        inst2    = re.compile("^[ \t]*INSTANCE[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*([A-Za-z0-9_]*)[ \t]*$")

        prminst = re.compile("^([A-Za-z_][A-Za-z0-9_]*)(,)")
        prmidx  = re.compile("^([A-Za-z_][A-Za-z0-9_]*?)([0-9_]+)(,)")
        prmeq   = re.compile("^([A-Za-z_][A-Za-z0-9_]*)=([^,]*)(,)")
        prmeqq  = re.compile('^([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"(,)')
        prmeqqq = re.compile("^([A-Za-z_][A-Za-z0-9_]*)='([^']*)'(,)")

        fp = myopen(file)
        if not fp:
            raise IOError, "File %s not found!" % ( file )
        lines = [l + "\n" for l in extra] + fp.readlines()
        fp.close()
        origlines = lines

        # Do the preliminary config expansion!
        output = StringIO.StringIO()
        expand(self, lines, output)
        value = output.getvalue()
        output.close()
        lines = value.split("\n")

        d = {"DIRNAME": self.dirname}
        for l in lines:
            l = l.strip()
            m = inst.search(l)
            if m != None:
                continue            # Skip instantiations for now!
            m = inst2.search(l)
            if m != None:           # First new-style instantiation --> we're done here!
                break
            # Search for a one-line assignment of some form!
            m = eqqq.search(l)
            if m == None:
                m = eqq.search(l)
                if m == None:
                    m = eq.search(l)
                    if m == None:
                        m = spqq.search(l)
                        if m == None:
                            m = spq.search(l)
                            if m == None:
                                m = sp.search(l)
            if m != None:
                var = m.group(1)
                val = m.group(2)
                d[var] = val;
                continue
            if l != "" and l[0] != '#':
                print "Skipping unknown line: %s" % l
        self.ddict = d

        # Now that we have the aliases, reprocess the config!
        
        lines = origlines
        output = StringIO.StringIO()
        expand(self, lines, output)
        value = output.getvalue()
        output.close()
        lines = value.split("\n")
        
        i = {}
        d = {"DIRNAME": self.dirname}
        nd = {}
        newstyle = False
        ininst   = False
        
        for l in lines:
            l = l.strip()
            m = inst2.search(l)
            if m != None:
                print "Found newstyle instance %s" % l
                newstyle = True
            if newstyle:
                if m != None:
                    if ininst:
                        print "Finishing instance of %s" % iname
                        self.finish_instance(iname, i, dd)
                    ininst = True
                    iname = m.group(1)
                    id = m.group(2)
                    print "Creating instance of %s" % iname
                    dd, n = self.create_instance(iname, id, i, nd)
                else:
                    loc = 0           # Look for parameters!
                    first = None
                    haveeq = False
                    while l[loc:] != '':
                        m = assign.search(l[loc:])
                        if m != None:
                            loc += m.end()
                            if haveeq:
                                print "Double equal sign in |%s|" % l
                            haveeq = True
                            continue   # Just ignore it!

                        m = wqq.search(l[loc:])
                        if m != None:
                            loc += m.end()
                        else:
                            m = wq.search(l[loc:])
                            if m != None:
                                loc += m.end() + 1
                            else:
                                m = w.search(l[loc:])
                                if m != None:
                                    loc += m.end() + 1
                                else:
                                    break        # How does this even happen?!?
                        val = m.group(1)
                        if first != None:
                            dd[first] = val
                            d[iname + first + n] = val
                            first = None
                        else:
                            # Could this be an instance parameter?
                            useinst = ''
                            usenum  = 0
                            try:
                                t = nd[val]
                                useinst = t[0]
                                usenum = t[1]
                            except:
                                m = prmidx.search(val+",")
                                if m != None:
                                    useinst = m.group(1)
                                    usenum = int(m.group(2))
                            try:
                                used = i[useinst][usenum]
                                for k in used.keys():
                                    var = useinst + k
                                    val = used[k]
                                    dd[var] = val
                            except:
                                first = val
                                haveeq = False
                continue
            m = inst.search(l)
            if m != None:
                id = m.group(2)
                iname = m.group(3)
                params = m.group(4) + ","
                dd, n = self.create_instance(iname, id, i, nd)
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
                            # This is an instance parameter.  It is either old-style,
                            # INSTn, or an arbitrary name.  Check the name dict first!
                            try:
                                t = nd[m.group(1)]
                                useinst = t[0]
                                usenum = t[1]
                                params = params[m.end(2):len(params)]
                            except:
                                m = prmidx.search(params)
                                if m == None:
                                    print "Unknown parameter in line %s" % params
                                    params = ""
                                    continue
                                useinst = m.group(1)
                                usenum = int(m.group(2))
                                params = params[m.end(3):len(params)]
                            # Find the instance, and add all of its named parameters
                            # VAL with the name INSTVAL.
                            used = i[useinst][usenum]
                            for k in used.keys():
                                var = useinst + k
                                val = used[k]
                                dd[var] = val
                        else:
                            print "Unknown parameter in line %s" % params
                            params = ""
                self.finish_instance(iname, i, dd)
                continue
            # Search for a one-line assignment of some form!
            m = eqqq.search(l)
            if m == None:
                m = eqq.search(l)
                if m == None:
                    m = eq.search(l)
                    if m == None:
                        m = spqq.search(l)
                        if m == None:
                            m = spq.search(l)
                            if m == None:
                                m = sp.search(l)
            if m != None:
                var = m.group(1)
                val = m.group(2)
                d[var] = val;
                continue
            if l != "" and l[0] != '#':
                print "Skipping unknown line: %s" % l
        if ininst:
            self.finish_instance(iname, i, dd)
        self.idict = i
        self.ddict = d


    def eval_expr(self, expr):
        return self.eval_(ast.parse(expr).body[0].value) # Module(body=[Expr(value=...)])

    def eval_(self, node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Name):
            try:
                x = int(self.ddict[node.id])
            except:
                x = 0
            return x
        elif isinstance(node, ast.operator):
            return self.operators[type(node)]
        elif isinstance(node, ast.BinOp):
            return self.eval_(node.op)(self.eval_(node.left), self.eval_(node.right))
        else:
            raise TypeError(node)

# Find the endre in the lines starting at index i, offset l.
# However, lb and rb are regular expressions that denote a region to be skipped.
# Note that endre might be equal to rb!
# Return a tuple: (newlines, newi, newloc), or None if it wasn't found.
def searchforend(lines, endre, lb, rb, i, l):
    j = i
    loc = l
    nest = 0
    newlines = []
    while j < len(lines):
        #
        # Looking at lines[j][loc:]!
        #
        lbm = lb.search(lines[j][loc:])
        if lbm != None:
            lbp = lbm.end(2)
        else:
            lbp = 100000
        if nest != 0:
            endm = rb.search(lines[j][loc:])
        else:
            endm = endre.search(lines[j][loc:])
        if endm != None:
            endp = endm.end(2)
        else:
            endp = 100000

        if lbp == 100000 and endp == 100000:
            # Nothing here!
            newlines.append(lines[j][loc:])
            j += 1
            loc = 0
            continue;
        if lbp < endp:
            # Found a new start!
            nest = nest + 1
            pos = loc
            loc += lbp
            if pos == 0 and lines[j][loc] == '\n':
                loc += 1
            newlines.append(lines[j][pos:loc])
            continue;
        else:
            # Found the end, either rb or endre!
            if nest != 0:
                # Must have been rb, close it out and continue.
                nest = nest - 1
                pos = loc
                loc += endp
                if pos == 0 and lines[j][loc] == '\n':
                    loc += 1
                newlines.append(lines[j][pos:loc])
                continue;
            # We're really done.  Strip off what we were looking for.
            newlines.append(endm.group(1))
            pos = loc
            loc += endp
            if pos == 0 and lines[j][loc:].strip() == "":
                # If the $$ directive is the entire line, don't add a newline!
                loc = 0;
                j += 1
            return (newlines, j, loc)
    return None

def rename_index(d):
    idxre = re.compile("^INDEX([0-9]*)")
    new = []
    val = []
    for k in d.keys():
        m = idxre.search(k)
        if m != None:
            arg = m.group(1)
            if arg == '':
                new.append("INDEX1")
            else:
                new.append("INDEX%d" % (int(arg) + 1))
            val.append(d[k])
            del d[k]
    for i in range(len(new)):
        d[new[i]] = val[i]
    return d

def expand(cfg, lines, f):
    i = 0
    loc = 0
    while i < len(lines):
        m = cfg.doubledollar.search(lines[i][loc:])
        if m == None:
            # Line without a $$.
            f.write("%s" % lines[i][loc:])
            i += 1
            loc = 0
            continue

        # Write the first part
        f.write(m.group(1))
        pos = loc + m.end(1)     # save where we found this!
        loc = pos + 2            # skip the '$$'!

        m = cfg.keyword.search(lines[i][loc:])
        if m != None:
            kw = m.group(1)
            if kw == None:
                kw = m.group(2)
                loc += m.end(2)      # Leave on the '{'!
            else:
                loc += m.end(1)      # Leave on the '('!
            
            if kw == "TRANSLATE":
                argm = cfg.trargs.search(lines[i][loc:])
                if argm != None:
                    loc += argm.end(3)+2
            elif kw == "CALC":
                argm = cfg.brackets.search(lines[i][loc:])
                if argm != None:
                    loc += argm.end(1)+1
            elif kw == "IF":
                argm = cfg.ifargs.search(lines[i][loc:])
                if argm != None:
                    kw = "TIF"    # Triple IF!
                    loc += argm.end(3)+1
                else:
                    argm = cfg.parens.search(lines[i][loc:])
                    if argm != None:
                        loc += argm.end(1)+1
                    if pos == 0 and lines[i][loc:].strip() == "":
                        # If the $$ directive is the entire line, don't add a newline!
                        loc = 0;
                        i += 1
            else:
                argm = cfg.parens.search(lines[i][loc:])
                if argm != None:
                    loc += argm.end(1)+1
                if pos == 0 and lines[i][loc:].strip() == "":
                    # If the $$ directive is the entire line, don't add a newline!
                    loc = 0;
                    i += 1
                    
            if argm != None:
                if kw == "LOOP":
                    iname = argm.group(1)
                    startloop = re.compile("(.*?)\$\$LOOP\(" + iname + "(\))")
                    endloop = re.compile("(.*?)\$\$ENDLOOP\(" + iname + "(\))")
                    t = searchforend(lines, endloop, startloop, endloop, i, loc)
                    if t == None:
                        print "Cannot find $$ENDLOOP(%s)?" % iname
                        sys.exit(1)
                    if iname[0] >= "0" and iname[0] <= "9":
                        try:
                            cnt = int(iname)
                        except:
                            cnt = 0
                        ilist = [{"INDEX": str(n)} for n in range(cnt)]
                    elif iname in cfg.idict.keys():
                        try:
                            ilist = cfg.idict[iname]
                        except:
                            ilist = []
                    else:
                        try:
                            cnt = int(cfg.ddict[iname])
                        except:
                            cnt = 0
                        ilist = [{"INDEX": str(n)} for n in range(cnt)]
                    olddict = cfg.ddict
                    for inst in ilist:
                        cfg.ddict = rename_index(olddict.copy())
                        cfg.ddict.update(inst)
                        expand(cfg, t[0], f)
                    cfg.ddict = olddict
                    i = t[1]
                    loc = t[2]
                elif kw == "IF":
                    iname = argm.group(1)
                    ifre = re.compile("(.*?)\$\$IF\(" + iname + "(\))")
                    endre = re.compile("(.*?)\$\$ENDIF\(" + iname + "(\))")
                    elsere = re.compile("(.*?)\$\$ELSE\(" + iname + "(\))")
                    t = searchforend(lines, endre, ifre, endre, i, loc)
                    if t == None:
                        print "Cannot find $$ENDIF(%s)?" % iname
                        sys.exit(1)
                    elset = searchforend(t[0], elsere, ifre, endre, 0, 0)
                    try:
                        v = cfg.ddict[iname]
                    except:
                        v = ""
                    if v != "":
                        # True, do the if!
                        if elset != None:
                            newlines = elset[0]
                        else:
                            newlines = t[0]
                        expand(cfg, newlines, f)
                    else:
                        # False, do the else!
                        if elset != None:
                            newlines = t[0][elset[1]:]
                            newlines[0] = newlines[0][elset[2]:]
                            expand(cfg, newlines, f)
                    i = t[1]
                    loc = t[2]
                elif kw == "TIF":
                    iname = argm.group(1)
                    newlines = []
                    try:
                        v = cfg.ddict[iname]
                    except:
                        v = ""
                    if v != "":
                        # True, do the if!
                        newlines.append(argm.group(2))
                    else:
                        # False, do the else!
                        newlines.append(argm.group(3))
                    expand(cfg, newlines, f)
                elif kw == "INCLUDE":
                    try:
                        fn = cfg.ddict[argm.group(1)]
                    except:
                        fn = argm.group(1)
                    try:
                        newlines=myopen(fn).readlines()
                        expand(cfg, newlines, f)
                    except:
                        print "Cannot open file %s!" % fn
                elif kw == "COUNT":
                    try:
                        cnt = str(len(cfg.idict[argm.group(1)]))
                    except:
                        cnt = "0"
                    f.write(cnt)
                elif kw == "CALC":
                    # Either $$CALC{expr} or $$CALC{expr,format}.
                    args = argm.group(1).split(",")
                    output = StringIO.StringIO()
                    expand(cfg, [args[0]], output)
                    value = output.getvalue()
                    output.close()
                    if len(args) > 1:
                        fmt = args[1]
                    else:
                        fmt = "%d"
                    try:
                        v = cfg.eval_expr(value)
                    except:
                        v = 0
                    f.write(fmt % (v))
                else: # Must be "TRANSLATE"
                    try:
                        val = cfg.ddict[argm.group(1)].translate(string.maketrans(argm.group(2), argm.group(3)))
                        f.write(val)
                    except:
                        pass
            else:
                print "Malformed $$%s statement?" % kw
                sys.exit(1)
            continue
        
        # Just a variable reference!
        if lines[i][loc] == "(":
            m = cfg.parens.search(lines[i][loc:])
        else:
            m = cfg.word.search(lines[i][loc:])
        if m != None:
            try:
                val = cfg.ddict[m.group(1)]
                f.write(val)
            except:
                pass
            if lines[i][loc] == '(':
                loc += m.end(1) + 1
            else:
                loc += m.end(1)
        else:
            print "Can't find variable name?!?"

if __name__ == '__main__':
    xp = os.getenv("EXPAND_PATH")
    if xp == None:
        expand_path = [".."]
    else:
        expand_path = xp.split(":") + [".."]
    av = sys.argv[1:]           # Drop expand.py
    if av[0] == '-c':
        configfile = av[1]      # -c CONFIG
        av = av[2:]
        name = os.path.basename(configfile)
        if name[-4:] == ".cfg":
            name = name[:-4]
        extra = "CONFIG=" + name
    else:
        configfile = "config" 
        extra = "CONFIG="
    if len(av) == 0 or av[0] == '-h':
        print "Usage: expand.py [ -c CONFIG ] TEMPLATE OUTFILE [ ADDITIONAL_STATEMENTS ]"
        print "   or: expand.py [ -c CONFIG ] NAME"
        sys.exit(1)
    try:
        if len(av) == 1:
            cfg=config()
            cfg.read_config(configfile, [])
            lines=['$$' + av[0] + '\n']
            expand(cfg, lines, sys.stdout)
            sys.exit(0)
        cfg=config()
        cfg.read_config(configfile, av[2:])
        lines=myopen(av[0]).readlines()
        fp = open(av[1], 'w')
        expand(cfg, lines, fp)
        fp.close()
        sys.exit(0)
    except IOError, e:
        print e
        sys.exit(1)

