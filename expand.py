#!/usr/bin/env python
import os
import sys
import re
import string
import ast
import operator
import StringIO

class config():
    def __init__(self, file, extra):
        d = {}
        i = {}
        d["DIRNAME"] = os.getcwd().split('/')[-1]
        try:
            fp = open(file)
        except:
            fp = open("../" + file)
        lines = extra + fp.readlines()
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
        self.ddict = d
        self.idict = i

        # Pre-define some regular expressions!
        self.doubledollar = re.compile("^(.*?)\$\$")
        self.keyword      = re.compile("^(LOOP|IF|INCLUDE|TRANSLATE|COUNT)\(|(CALC)\{")
        self.parens       = re.compile("^\(([^)]*?)\)")
        self.brackets     = re.compile("^\{([^}]*?)\}")
        self.trargs       = re.compile('^\(([^,]*?),"([^"]*?)","([^"]*?)"\)')
        self.ifargs       = re.compile('^\(([^,]*?),([^,]*?),([^)]*?)\)')
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

# Fine the endre in the lines starting at index i, offset l.
# Return a tuple: (newlines, newi, newloc), or
# None if it wasn't found.
def searchforend(lines, endre, i, l):
    j = i
    loc = l
    newlines = []
    while j < len(lines):
        endm = endre.search(lines[j][loc:])
        if endm == None:
            newlines.append(lines[j][loc:])
            j += 1
            loc = 0
        else:
            newlines.append(endm.group(1))
            pos = loc
            loc += endm.end(2)
            if pos == 0 and lines[j][loc:].strip() == "":
                # If the $$ directive is the entire line, don't add a newline!
                loc = 0;
                j += 1
            return (newlines, j, loc)
    return None

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
                    endloop = re.compile("(.*?)\$\$ENDLOOP\(" + iname + "(\))")
                    t = searchforend(lines, endloop, i, loc)
                    if t == None:
                        print "Cannot find $$ENDLOOP(%s)?" % iname
                        sys.exit(1)
                    try:
                        ilist = cfg.idict[iname]
                    except:
                        ilist = []
                    olddict = cfg.ddict
                    for inst in ilist:
                        cfg.ddict = olddict.copy()
                        cfg.ddict.update(inst)
                        expand(cfg, t[0], f)
                    cfg.ddict = olddict
                    i = t[1]
                    loc = t[2]
                elif kw == "IF":
                    iname = argm.group(1)
                    endre = re.compile("(.*?)\$\$ENDIF\(" + iname + "(\))")
                    elsere = re.compile("(.*?)\$\$ELSE\(" + iname + "(\))")
                    t = searchforend(lines, endre, i, loc)
                    if t == None:
                        print "Cannot find $$ENDIF(%s)?" % iname
                        sys.exit(1)
                    elset = searchforend(t[0], elsere, 0, 0)
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
                        newlines=open(fn).readlines()
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
    av = sys.argv;
    if len(av) < 3:
        print "Usage: expand.py TEMPLATE OUTFILE [ ADDITIONAL_STATEMENTS ]"
        sys.exit(1)
    cfg=config("config", sys.argv[3:])
    lines=open(sys.argv[1]).readlines()
    fp = open(sys.argv[2], 'w')
    expand(cfg, lines, fp)
    sys.exit(0)
