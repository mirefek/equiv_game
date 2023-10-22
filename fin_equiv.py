import random
import itertools
from collections import defaultdict

def binom(n,k):
    if k < 0 or k > n: return 0
    res = 1
    k = min(k, n-k)
    for i in range(k):
        res = (res * (n-i)) // (i+1)
    return res
def binom_index(n,subset):
    k = len(subset)
    if k == 0: return 0
    elif subset[-1] < n-1:
        return binom_index(n-1,subset)
    else:
        return binom_index(n-1,subset[:-1])+binom(n-1,k)
def subset_at_binom_index(n,k,index):
    assert n >= 0
    assert k >= 0
    assert k <= n
    assert 0 <= index < binom(n,k)
    if k == 0:
        assert index == 0
        return []
    # use: binom(n,k) = binom(n-1,k-1) + binom(n-1,k)
    x = binom(n-1,k)
    if index < x:
        res = subset_at_binom_index(n-1,k,index)
    else:
        res = subset_at_binom_index(n-1,k-1,index-x)
        res.append(n-1)
    return res

bell_number_l = [1]
def bell_number(n):
    assert n >= 0
    while len(bell_number_l) <= n:
        bell_number_l.append(_calculate_bell_number(len(bell_number_l)))
    return bell_number_l[n]
def _calculate_bell_number(n):
    return sum(binom(n-1,k) * bell_number_l[k] for k in range(n))

class FinEquiv:
    def __init__(self, num_nodes, classes):
        self.num_nodes = num_nodes
        self.nodes = range(num_nodes)
        self.classes = tuple(sorted(tuple(sorted(c)) for c in classes))
        assert all(len(c) > 0 for c in self.classes)

        self.node_to_class = [None]*num_nodes
        for i,c in enumerate(self.classes):
            for x in c:
                assert self.node_to_class[x] is None
                self.node_to_class[x] = i
        assert None not in self.node_to_class

        self.isolated_nodes = tuple(
            c[0] for c in self.classes if len(c) == 1
        )
        self.nontriv_classes = tuple(
            c for c in self.classes if len(c) > 1
        )

    def __str__(self):
        items = []
        items.extend(
            '('+' ~ '.join(map(str, c))+')'
            for c in self.nontriv_classes
        )
        items.extend(str(x) for x in self.isolated_nodes)
        return ', '.join(items)

    def __eq__(self, other):
        return isinstance(other, FinEquiv) and self.classes == other.classes
    def __hash__(self):
        return hash(self.classes)

    def relates(self, a,b):
        return self.node_to_class[a] == self.node_to_class[b]

    def __or__(self, other):
        assert self.num_nodes == other.num_nodes
        return self.generated_by(
            self.num_nodes,
            *itertools.chain(self.classes, other.classes)
        )
    def __and__(self, other):
        assert self.num_nodes == other.num_nodes
        classes = []
        for c in self.classes:
            refinement = defaultdict(list)
            for x in c:
                refinement[other.node_to_class[x]].append(x)
            classes.extend(refinement.values())
        return FinEquiv(self.num_nodes, classes)

    @staticmethod
    def generated_by(num_nodes, *classes):
        graph = [
            []
            for x in range(num_nodes)
        ]
        for c in classes: # convert given classes to a graph
            c = tuple(c)
            if len(c) > 1:
                x = c[0]
                for y in c[1:]:
                    graph[x].append(y)
                    graph[y].append(x)

        # convert graph to output classes
        classes = []
        used = [False]*num_nodes
        for main in range(num_nodes):
            if used[main]: continue
            c = []
            stack = [main]
            while stack:
                x = stack.pop()
                if used[x]: continue
                used[x] = True
                c.append(x)
                stack.extend(graph[x])
            classes.append(c)

        return FinEquiv(num_nodes, classes)

    @staticmethod
    def empty(num_nodes):
        return FinEquiv(num_nodes, [[x] for x in range(num_nodes)])
    @staticmethod
    def full(num_nodes):
        return FinEquiv(num_nodes, [range(num_nodes)])

    @staticmethod
    def all_equiv_classes(num_nodes):
        assert num_nodes >= 0
        if num_nodes == 0:
            yield ()
        else:
            x = (num_nodes-1,)
            for rec_classes in FinEquiv.all_equiv_classes(num_nodes-1):
                yield rec_classes+(x,)
                for i,c in enumerate(rec_classes):
                    yield rec_classes[:i] + (c+x,) + rec_classes[i+1:]

    @staticmethod
    def collect_all(num_nodes):
        return [
            FinEquiv(num_nodes, classes)
            for classes in FinEquiv.all_equiv_classes(num_nodes)
        ]

    @staticmethod
    def generate_lattice(generators):
        stack = len(generators)
        seen = set(stack)
        while stack:
            x = stack.pop()
            added = []
            added.extend([x & y for y in seen])
            added.extend([x | y for y in seen])
            added = [y for y in added if x not in seen]
            stack.extend(added)
            seen.update(added)

    # indexing & uniform random generation

    def insert_class(self, inserted):
        num_nodes = self.num_nodes + len(inserted)
        nodes = set(range(num_nodes))
        inserted_s = set(inserted)
        assert inserted_s <= nodes
        remaining = sorted(nodes - inserted_s)
        classes = [
            [remaining[x] for x in c]
            for c in self.classes
        ] + [inserted]
        return FinEquiv(num_nodes, classes)
    def drop_class(self, dropped_i):
        dropped = self.classes[dropped_i]
        nodes = set(self.nodes) - set(dropped)
        ori_to_new = [None]*self.num_nodes
        for i,n in enumerate(sorted(nodes)):
            ori_to_new[n] = i
        classes = [
            [ori_to_new[x] for x in c]
            for ci,c in enumerate(self.classes)
            if ci != dropped_i
        ]
        return FinEquiv(len(nodes), classes)

    def get_index(self):
        n = self.num_nodes
        if n == 0: return 0
        
        # find class with the last element
        ci,c = next((i,c) for i,c in enumerate(self.classes) if self.num_nodes-1 in c)
        c = c[:-1] # remove the 'n-1' element

        # get base index
        rest = self.drop_class(ci)
        index = rest.get_index()
        index = index * binom(n-1, len(c)) + binom_index(n-1, c)

        # account for the previous summands
        index += sum(binom(n-1,k) * bell_number(k) for k in range(n-1-len(c)))

        return index

    @staticmethod
    def at_index(n, index):
        assert 0 <= index < bell_number(n)
        if n == 0: return FinEquiv(0, ())
        for k in range(n):
            x = binom(n-1,k) * bell_number(k)
            if index < x: break
            index -= x

        x = binom(n-1, n-k-1)
        rest_index = index // x
        class_index = index % x
        c = subset_at_binom_index(n-1,n-1-k,class_index)+[n-1]
        rest = FinEquiv.at_index(k, rest_index)
        return rest.insert_class(c)

    @staticmethod
    def random(num_nodes):
        return FinEquiv.at_index(num_nodes, random.randrange(bell_number(num_nodes)))

if __name__ == "__main__":

    for i in range(bell_number(5)):
        eq = FinEquiv.at_index(5,i)
        assert eq.get_index() == i

    eqs = FinEquiv.collect_all(5)
    # for eq in eqs: print(eq.get_index(), ':', eq)
    indices = set(eq.get_index() for eq in eqs)
    print(len(eqs))
    eq1 = FinEquiv.random(10)
    eq2 = FinEquiv.random(10)
    print('eq1:', eq1)
    print('eq2:', eq2)
    print('eq1 & eq2:', eq1 & eq2)
    print('eq1 | eq2:', eq1 | eq2)

    for n in range(10):
        print(n, bell_number(n))
