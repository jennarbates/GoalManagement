"""Runs every solution in leetcode_bank.py against test cases, including the
printed examples. Run: python3 test_leetcode_bank.py"""
import heapq
from typing import List, Optional

import leetcode_bank


class ListNode:
    def __init__(self, val=0, next=None):
        self.val, self.next = val, next


class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val, self.left, self.right = val, left, right


def make_list(vals, cycle_to=None):
    nodes = [ListNode(v) for v in vals]
    for a, b in zip(nodes, nodes[1:]):
        a.next = b
    if cycle_to is not None and nodes:
        nodes[-1].next = nodes[cycle_to]
    return nodes[0] if nodes else None


def list_vals(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


def make_tree(level):
    """LeetCode-style level order, None for missing children."""
    if not level:
        return None
    nodes = [TreeNode(v) if v is not None else None for v in level]
    kids = iter(nodes[1:])
    for node in nodes:
        if node:
            node.left = next(kids, None)
            node.right = next(kids, None)
    return nodes[0]


def tree_level(root):
    out, q = [], [root]
    while q:
        n = q.pop(0)
        out.append(n.val if n else None)
        if n:
            q += [n.left, n.right]
    while out and out[-1] is None:
        out.pop()
    return out


def load(problem, bad_from=None):
    ns = {"List": List, "Optional": Optional, "heapq": heapq,
          "ListNode": ListNode, "TreeNode": TreeNode,
          "isBadVersion": lambda v: v >= bad_from}
    exec(problem["solution"], ns)
    return ns


def sol(p, **kw):
    return load(p, **kw)["Solution"]()


P = {p["id"]: p for p in leetcode_bank.EASY}
checks = []


def check(pid, got, want):
    checks.append((pid, got == want, got, want))


s = sol(P["contains-duplicate"])
check("contains-duplicate", s.containsDuplicate([4, 7, 1, 7]), True)
check("contains-duplicate", s.containsDuplicate([3, 8, 5]), False)
check("contains-duplicate", s.containsDuplicate([1]), False)

s = sol(P["valid-anagram"])
check("valid-anagram", s.isAnagram("listen", "silent"), True)
check("valid-anagram", s.isAnagram("hello", "hallo"), False)
check("valid-anagram", s.isAnagram("ab", "abc"), False)

s = sol(P["two-sum"])
check("two-sum", s.twoSum([3, 9, 5, 1], 6), [2, 3])
check("two-sum", s.twoSum([4, 4], 8), [0, 1])
check("two-sum", s.twoSum([-3, 4, 3, 90], 0), [0, 2])

s = sol(P["longest-common-prefix"])
check("longest-common-prefix", s.longestCommonPrefix(["flight", "flow", "flower"]), "fl")
check("longest-common-prefix", s.longestCommonPrefix(["car", "dog"]), "")
check("longest-common-prefix", s.longestCommonPrefix(["", "a"]), "")
check("longest-common-prefix", s.longestCommonPrefix(["solo"]), "solo")

s = sol(P["valid-palindrome"])
check("valid-palindrome", s.isPalindrome("Was it a car or a cat I saw?"), True)
check("valid-palindrome", s.isPalindrome("Not a palindrome"), False)
check("valid-palindrome", s.isPalindrome(" "), True)
check("valid-palindrome", s.isPalindrome("0P"), False)

s = sol(P["reverse-string"])
x = list("code"); s.reverseString(x); check("reverse-string", x, list("edoc"))
x = list("a"); s.reverseString(x); check("reverse-string", x, ["a"])

s = sol(P["move-zeroes"])
x = [0, 5, 0, 3, 12]; s.moveZeroes(x); check("move-zeroes", x, [5, 3, 12, 0, 0])
x = [0]; s.moveZeroes(x); check("move-zeroes", x, [0])

s = sol(P["merge-sorted-array"])
x = [2, 5, 9, 0, 0]; s.merge(x, 3, [1, 6], 2); check("merge-sorted-array", x, [1, 2, 5, 6, 9])
x = [0]; s.merge(x, 0, [1], 1); check("merge-sorted-array", x, [1])
x = [1]; s.merge(x, 1, [], 0); check("merge-sorted-array", x, [1])

s = sol(P["best-time-to-buy-and-sell-stock"])
check("best-time-to-buy-and-sell-stock", s.maxProfit([8, 3, 6, 1, 5, 4]), 4)
check("best-time-to-buy-and-sell-stock", s.maxProfit([9, 7, 4, 2]), 0)

s = sol(P["contains-duplicate-ii"])
check("contains-duplicate-ii", s.containsNearbyDuplicate([5, 1, 5, 2], 2), True)
check("contains-duplicate-ii", s.containsNearbyDuplicate([5, 1, 2, 5], 2), False)
check("contains-duplicate-ii", s.containsNearbyDuplicate([1, 1], 0), False)
check("contains-duplicate-ii", s.containsNearbyDuplicate([1, 0, 1, 1], 1), True)

s = sol(P["valid-parentheses"])
check("valid-parentheses", s.isValid("{[()]}"), True)
check("valid-parentheses", s.isValid("([)]"), False)
check("valid-parentheses", s.isValid("(("), False)
check("valid-parentheses", s.isValid("]"), False)

ns = load(P["implement-queue-using-stacks"])
q = ns["MyQueue"](); q.push(4); q.push(7)
check("implement-queue-using-stacks", [q.peek(), q.pop(), q.empty(), q.pop(), q.empty()], [4, 4, False, 7, True])

s = sol(P["remove-all-adjacent-duplicates-in-string"])
check("remove-all-adjacent-duplicates-in-string", s.removeDuplicates("xyyxz"), "z")
check("remove-all-adjacent-duplicates-in-string", s.removeDuplicates("aabccb"), "")

s = sol(P["binary-search"])
check("binary-search", s.search([-4, 0, 2, 7, 11], 7), 3)
check("binary-search", s.search([-4, 0, 2, 7, 11], 5), -1)
check("binary-search", s.search([5], 5), 0)

s = sol(P["search-insert-position"])
for t, want in [(8, 2), (5, 2), (12, 4), (1, 0)]:
    check("search-insert-position", s.searchInsert([2, 4, 8, 10], t), want)

check("first-bad-version", sol(P["first-bad-version"], bad_from=4).firstBadVersion(6), 4)
check("first-bad-version", sol(P["first-bad-version"], bad_from=1).firstBadVersion(1), 1)
check("first-bad-version", sol(P["first-bad-version"], bad_from=7).firstBadVersion(7), 7)

ns = load(P["reverse-linked-list"])
s = ns["Solution"]()
check("reverse-linked-list", list_vals(s.reverseList(make_list([7, 3, 9]))), [9, 3, 7])
check("reverse-linked-list", list_vals(s.reverseList(None)), [])

s = sol(P["merge-two-sorted-lists"])
check("merge-two-sorted-lists", list_vals(s.mergeTwoLists(make_list([1, 4, 6]), make_list([2, 3, 7]))), [1, 2, 3, 4, 6, 7])
check("merge-two-sorted-lists", list_vals(s.mergeTwoLists(None, make_list([0]))), [0])

s = sol(P["linked-list-cycle"])
check("linked-list-cycle", s.hasCycle(make_list([3, 8, 5, 2], cycle_to=1)), True)
check("linked-list-cycle", s.hasCycle(make_list([3, 8])), False)
check("linked-list-cycle", s.hasCycle(None), False)

s = sol(P["middle-of-the-linked-list"])
check("middle-of-the-linked-list", s.middleNode(make_list([10, 20, 30, 40, 50])).val, 30)
check("middle-of-the-linked-list", s.middleNode(make_list([10, 20, 30, 40, 50, 60])).val, 40)

s = sol(P["maximum-depth-of-binary-tree"])
check("maximum-depth-of-binary-tree", s.maxDepth(make_tree([5, 3, 8, None, None, 7, 9])), 3)
check("maximum-depth-of-binary-tree", s.maxDepth(None), 0)

s = sol(P["invert-binary-tree"])
check("invert-binary-tree", tree_level(s.invertTree(make_tree([5, 3, 8, 1, 4]))), [5, 8, 3, None, None, 4, 1])

s = sol(P["same-tree"])
check("same-tree", s.isSameTree(make_tree([1, 2, 3]), make_tree([1, 2, 3])), True)
check("same-tree", s.isSameTree(make_tree([1, 2]), make_tree([1, None, 2])), False)

s = sol(P["balanced-binary-tree"])
check("balanced-binary-tree", s.isBalanced(make_tree([5, 3, 8, None, None, 7, 9])), True)
check("balanced-binary-tree", s.isBalanced(make_tree([1, 2, None, 3, None, 4])), False)
check("balanced-binary-tree", s.isBalanced(None), True)

s = sol(P["diameter-of-binary-tree"])
check("diameter-of-binary-tree", s.diameterOfBinaryTree(make_tree([6, 2, 9, 1, 4])), 3)
check("diameter-of-binary-tree", s.diameterOfBinaryTree(make_tree([1])), 0)

s = sol(P["last-stone-weight"])
check("last-stone-weight", s.lastStoneWeight([3, 5, 8, 2]), 2)
check("last-stone-weight", s.lastStoneWeight([4, 4]), 0)
check("last-stone-weight", s.lastStoneWeight([1]), 1)

s = sol(P["flood-fill"])
check("flood-fill", s.floodFill([[1, 1, 0], [1, 0, 0], [1, 1, 1]], 0, 0, 2), [[2, 2, 0], [2, 0, 0], [2, 2, 2]])
check("flood-fill", s.floodFill([[0, 0], [0, 0]], 0, 0, 0), [[0, 0], [0, 0]])

s = sol(P["climbing-stairs"])
check("climbing-stairs", [s.climbStairs(n) for n in (1, 2, 3, 4, 5)], [1, 2, 3, 5, 8])

s = sol(P["min-cost-climbing-stairs"])
check("min-cost-climbing-stairs", s.minCostClimbingStairs([5, 10, 3, 8]), 8)
check("min-cost-climbing-stairs", s.minCostClimbingStairs([10, 15, 20]), 15)

s = sol(P["single-number"])
check("single-number", s.singleNumber([7, 3, 7]), 3)
check("single-number", s.singleNumber([2, 9, 4, 9, 2]), 4)

s = sol(P["missing-number"])
check("missing-number", s.missingNumber([4, 2, 0, 1]), 3)
check("missing-number", s.missingNumber([1]), 0)

tested = {pid for pid, *_ in checks}
untested = set(P) - tested
failed = [c for c in checks if not c[1]]
for pid, ok, got, want in failed:
    print(f"FAIL {pid}: got {got!r}, want {want!r}")
print(f"{len(checks) - len(failed)}/{len(checks)} checks passed across {len(tested)} problems"
      + (f"; UNTESTED: {sorted(untested)}" if untested else ""))
raise SystemExit(1 if failed or untested else 0)
