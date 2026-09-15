r"""
Aho-Corasick: find every occurrence of many patterns in a single pass.

Build   a trie of all patterns (patterns that share a prefix share nodes),
        then give every node a failure link, computed breadth-first.
Search  walk the text one character at a time: follow a trie edge if one
        exists for the character, otherwise follow failure links until one
        does (or the root is reached), then report every pattern ending at
        the current node.

        root
       /    \
      r      d          "react", "redux" and "django":
      |      |          "react" and "redux" share r -> e.
      e      j
     / \     |
    a   d    a
    ...

Time    O(m) to build for a total pattern length m, and O(n + z) to search
        a text of length n with z matches, however many patterns there are.
        Scanning once per pattern instead is O(n * p) for p patterns.
"""

from collections import deque

ROOT = 0


class AhoCorasick:
    def __init__(self, patterns):
        self.patterns = list(patterns)
        # Parallel lists indexed by node number; node 0 is the root.
        self.children = [{}]  # node -> {character: child node}
        self.fail = [ROOT]  # node -> node for the longest proper suffix that is also a prefix
        self.outputs = [[]]  # node -> indexes of patterns that end at this node

        for index, pattern in enumerate(self.patterns):
            if not pattern:
                raise ValueError("Aho-Corasick patterns must be non-empty")
            self._insert(pattern, index)
        self._build_failure_links()

    @property
    def node_count(self):
        return len(self.children)

    def _insert(self, pattern, index):
        node = ROOT
        for character in pattern:
            if character not in self.children[node]:
                self.children.append({})
                self.fail.append(ROOT)
                self.outputs.append([])
                self.children[node][character] = len(self.children) - 1
            node = self.children[node][character]
        self.outputs[node].append(index)

    def _build_failure_links(self):
        # WHY breadth-first: a node's failure link always points to a shorter
        # string (a proper suffix), which sits closer to the root. Visiting
        # nodes in order of depth guarantees the failure link a node depends
        # on has already been computed.
        queue = deque()
        for child in self.children[ROOT].values():
            self.fail[child] = ROOT  # depth-1 nodes can only fall back to the root
            queue.append(child)

        while queue:
            node = queue.popleft()
            for character, child in self.children[node].items():
                queue.append(child)

                # The child spells (node's string + character). Its failure link
                # is the longest proper suffix of that which is also a path in
                # the trie: try the node's own suffixes, longest first.
                fallback = self.fail[node]
                while fallback != ROOT and character not in self.children[fallback]:
                    fallback = self.fail[fallback]
                self.fail[child] = self.children[fallback].get(character, ROOT)

                # A pattern ending at the failure node also ends here:
                # reaching "she" means "he" has just been read too.
                self.outputs[child] = self.outputs[child] + self.outputs[self.fail[child]]

    def search(self, text):
        """Yield (start, end, pattern index) for every occurrence, ordered by end."""
        node = ROOT
        for position, character in enumerate(text):
            # WHY failure links instead of restarting at the root: the
            # characters already read are never re-read. When the next
            # character breaks the current branch, the failure link jumps to
            # the longest suffix of what was read that can still continue.
            while node != ROOT and character not in self.children[node]:
                node = self.fail[node]
            node = self.children[node].get(character, ROOT)

            end = position + 1
            for index in self.outputs[node]:
                yield end - len(self.patterns[index]), end, index
