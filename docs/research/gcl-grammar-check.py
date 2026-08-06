# Grammar coverage check for the GCL condition renderer -- RESEARCH ARTIFACT, NOT PRODUCTION CODE.
#
# Implements exactly the grammar in docs/research/gcl-rendering-target.md section 6 and runs it
# over every condition-bearing field in samples/, to verify the claim that the grammar covers the
# corpus. It is an acceptor only: it builds no AST and renders nothing.
#
# Usage: python docs/research/gcl-grammar-check.py <repo-root>
# Expected: 55 distinct condition strings, 55 parsed, 0 failed.
#
# Do not grow this into the real parser -- see issue #6 for where parsing actually lands.
import json, glob, os, re, sys

TOKEN = re.compile(r"""
    \s+
  | (?P<INT>\d+)
  | (?P<IDENT>\\?[A-Za-z_][A-Za-z0-9_]*)
  | (?P<OP><==>|==>|<=|>=|==|!=|&&|\|\||[-+*/%<>!().,;\[\]])
""", re.X)


def lex(s):
    toks, i = [], 0
    while i < len(s):
        m = TOKEN.match(s, i)
        if not m:
            raise SyntaxError("bad char %r at %d" % (s[i], i))
        i = m.end()
        for k in ('INT', 'IDENT', 'OP'):
            if m.group(k) is not None:
                toks.append((k, m.group(k), m.start()))
    toks.append(('EOF', None, len(s)))
    return toks


class P:
    def __init__(self, s):
        self.t = lex(s)
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def at(self, v):
        return self.t[self.i][1] == v

    def eat(self, v=None):
        k, tv, pos = self.t[self.i]
        if v is not None and tv != v:
            raise SyntaxError("expected %r got %r at %d" % (v, tv, pos))
        self.i += 1
        return tv

    # expr := equivalence
    def expr(self):
        return self.equivalence()

    def equivalence(self):
        n = self.implication()
        while self.at('<==>'):
            self.eat(); self.implication()
        return n

    def implication(self):          # RIGHT-assoc
        n = self.disjunction()
        if self.at('==>'):
            self.eat(); self.implication()
        return n

    def disjunction(self):
        n = self.conjunction()
        while self.at('||'):
            self.eat(); self.conjunction()
        return n

    def conjunction(self):
        n = self.equality()
        while self.at('&&'):
            self.eat(); self.equality()
        return n

    def equality(self):
        n = self.relational()
        while self.peek()[1] in ('==', '!='):
            self.eat(); self.relational()
        return n

    def relational(self):
        n = self.additive()
        while self.peek()[1] in ('<', '>', '<=', '>='):
            self.eat(); self.additive()
        return n

    def additive(self):
        n = self.multiplicative()
        while self.peek()[1] in ('+', '-'):
            self.eat(); self.multiplicative()
        return n

    def multiplicative(self):
        n = self.unary()
        while self.peek()[1] in ('*', '/', '%'):
            self.eat(); self.unary()
        return n

    def unary(self):
        if self.peek()[1] in ('!', '-', '+'):
            self.eat(); return self.unary()
        return self.postfix()

    def postfix(self):
        n = self.primary()
        while True:
            if self.at('['):
                self.eat(); self.expr(); self.eat(']')
            elif self.at('.'):
                self.eat()
                if self.peek()[0] != 'IDENT':
                    raise SyntaxError("field name expected at %d" % self.peek()[2])
                self.eat()
            elif self.at('('):
                self.eat(); self.arglist(); self.eat(')')
            else:
                return n

    def arglist(self):
        if self.at(')'):
            return
        self.expr()
        while self.at(','):
            self.eat(); self.expr()

    def primary(self):
        k, v, pos = self.peek()
        if k == 'INT':
            self.eat(); return 'int'
        if self.at('('):
            save = self.i
            self.eat()
            if self.peek()[1] in ('\\forall', '\\exists'):
                return self.quantifier_tail()
            self.i = save
            self.eat('('); self.expr(); self.eat(')')
            return 'paren'
        if k == 'IDENT':
            self.eat(); return 'ident'
        raise SyntaxError("unexpected %r at %d" % (v, pos))

    # '(' already eaten; at \forall / \exists
    def quantifier_tail(self):
        self.eat()                      # \forall | \exists
        if self.peek()[0] != 'IDENT':
            raise SyntaxError("quantifier type expected at %d" % self.peek()[2])
        self.eat()                      # type
        while self.at('['):
            self.eat(); self.eat(']')
        if self.peek()[0] != 'IDENT':
            raise SyntaxError("quantifier var expected at %d" % self.peek()[2])
        self.eat()                      # var
        self.eat(';')
        self.expr()
        if self.at(';'):                # optional JML range;body form
            self.eat(); self.expr()
        self.eat(')')
        return 'quant'

    def parse(self):
        n = self.expr()
        if self.peek()[0] != 'EOF':
            raise SyntaxError("trailing %r at %d" % (self.peek()[1], self.peek()[2]))
        return n


CONDFIELDS = {'preCondition', 'postCondition', 'condition', 'intermediateCondition',
              'invariant', 'variant', 'guards', 'globalConditions'}

found = {}


def walk(o, src):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in CONDFIELDS:
                for s in ([v] if isinstance(v, str) else
                          [x for x in v if isinstance(x, str)] if isinstance(v, list) else []):
                    if s.strip():
                        found.setdefault(s, set()).add((src, k))
            walk(v, src)
    elif isinstance(o, list):
        for i in o:
            walk(i, src)


root = sys.argv[1] if len(sys.argv) > 1 else '.'
for f in sorted(glob.glob(os.path.join(root, 'samples', '*.json'))):
    walk(json.load(open(f, encoding='utf-8')), os.path.basename(f)[:-5])

ok = fail = 0
for s in sorted(found):
    try:
        P(s).parse()
        ok += 1
    except SyntaxError as e:
        fail += 1
        print('FAIL %-60s %s   [%s]' % (repr(s)[:60], e, sorted(found[s])))

print()
print('distinct condition strings: %d' % len(found))
print('parsed OK: %d    failed: %d' % (ok, fail))
