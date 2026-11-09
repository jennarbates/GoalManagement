"""LeetCode problem bank for the daily workbook.

Problems are grouped by pattern and listed in learning order (the order the
workbook hands them out). Statements and examples are written in my own words;
`lc` and `slug` point to the real problem so you can submit it online.

Each solution is checked by test_leetcode_bank.py. Add a level (e.g. "medium")
to LEVELS when you're ready to move up.
"""
from textwrap import dedent

PATTERNS = {
    "Arrays & Hashing": "Use a hash set or hash map to remember what you've seen. It turns 'search the whole array again' (O(n)) into a single lookup (O(1)). Reach for it when a problem asks about duplicates, counts, or pairs.",
    "Two Pointers": "Keep two indexes, often one at each end, and move them toward each other (or one reads while the other writes). Reach for it on sorted arrays, palindromes, and in-place rearranging.",
    "Sliding Window": "Track a contiguous range [left, right] that slides along the array, updating a running answer instead of recomputing it. Reach for it with 'best subarray/substring' or 'within k positions' questions.",
    "Stack": "Last in, first out. Push things you still need to match or undo, and pop when you find the match. Reach for it with brackets, 'remove adjacent', or anything that nests.",
    "Binary Search": "On sorted data, check the middle and throw away the half that can't contain the answer, so it takes O(log n) steps. Reach for it whenever the input is sorted or the answer flips from 'no' to 'yes' at one point.",
    "Linked List": "Nodes point to the next node, so you can't index. Use a dummy head node, and the slow/fast pointer trick to find middles and cycles. Draw boxes and arrows before you code.",
    "Trees": "Most tree problems are recursion: solve for the left and right subtrees, then combine at the node. Ask 'what does each call return?' before writing any code.",
    "Heap / Priority Queue": "A heap always gives you the smallest (or largest) item in O(log n). Reach for it when you repeatedly need 'the biggest so far' or 'the top k'.",
    "Graphs": "Grids and networks. Use BFS or DFS from a start cell, marking cells as visited so you never process one twice.",
    "1-D Dynamic Programming": "Write the answer for step i using answers for smaller steps (like i-1 and i-2), then build up from the base cases. If you only need the last two answers, keep two variables instead of a table.",
    "Bit Manipulation": "XOR cancels equal numbers (x ^ x = 0, x ^ 0 = x). Math tricks like the sum of 0..n can also replace extra memory.",
}

def _code(s: str) -> str:
    return dedent(s).strip("\n")


EASY = [
    # ── Arrays & Hashing ────────────────────────────────────────────────────
    {
        "id": "contains-duplicate", "lc": 217, "title": "Contains Duplicate", "slug": "contains-duplicate",
        "pattern": "Arrays & Hashing",
        "statement": "You get a list of integers nums. Return True if any value shows up at least twice, and False if every value is different.",
        "examples": [("nums = [4, 7, 1, 7]", "True", "7 appears twice."),
                     ("nums = [3, 8, 5]", "False", "All values are different.")],
        "constraints": "1 <= len(nums) <= 100,000",
        "hints": ["Checking every pair works, but how many pairs are there? That's O(n^2).",
                  "What data structure can tell you 'have I seen this number before?' instantly?",
                  "Walk through nums once with a set of values seen so far. If the current value is already in the set, you're done."],
        "approach": ["Make an empty set called seen.", "For each number: if it's in seen, return True; otherwise add it.", "If the loop finishes, there were no duplicates: return False."],
        "solution": _code('''
            class Solution:
                def containsDuplicate(self, nums: List[int]) -> bool:
                    seen = set()
                    for x in nums:
                        if x in seen:
                            return True
                        seen.add(x)
                    return False
        '''),
        "time": "O(n)", "space": "O(n)",
        "takeaway": "A hash set gives instant 'seen it before?' answers. You trade memory for speed.",
    },
    {
        "id": "valid-anagram", "lc": 242, "title": "Valid Anagram", "slug": "valid-anagram",
        "pattern": "Arrays & Hashing",
        "statement": "Given two strings s and t, return True if t uses exactly the same letters as s, the same number of times each, in any order.",
        "examples": [('s = "listen", t = "silent"', "True", "Same letters, rearranged."),
                     ('s = "hello", t = "hallo"', "False", "t has an 'a' where s has an 'e'.")],
        "constraints": "1 <= len(s), len(t) <= 50,000; lowercase English letters",
        "hints": ["If the lengths differ, can they possibly be anagrams?",
                  "Anagrams have the same count of every letter.",
                  "Count the letters of s in a dictionary, then walk t and subtract. If a count would go below zero, it's not an anagram."],
        "approach": ["If len(s) != len(t), return False.", "Count each letter of s in a dict.", "For each letter of t: if its count is 0, return False; otherwise subtract 1.", "Return True."],
        "solution": _code('''
            class Solution:
                def isAnagram(self, s: str, t: str) -> bool:
                    if len(s) != len(t):
                        return False
                    count = {}
                    for c in s:
                        count[c] = count.get(c, 0) + 1
                    for c in t:
                        if count.get(c, 0) == 0:
                            return False
                        count[c] -= 1
                    return True
        '''),
        "time": "O(n)", "space": "O(1), at most 26 letters",
        "takeaway": "A frequency map (letter -> count) is the standard tool for 'same items, different order' questions.",
    },
    {
        "id": "two-sum", "lc": 1, "title": "Two Sum", "slug": "two-sum",
        "pattern": "Arrays & Hashing",
        "statement": "Given a list of integers nums and an integer target, return the indexes of the two numbers that add up to target. There is exactly one answer, and you can't use the same element twice.",
        "examples": [("nums = [3, 9, 5, 1], target = 6", "[2, 3]", "nums[2] + nums[3] = 5 + 1 = 6."),
                     ("nums = [4, 4], target = 8", "[0, 1]", "The two 4s are different elements.")],
        "constraints": "2 <= len(nums) <= 10,000; exactly one valid answer",
        "hints": ["The brute force tries every pair. Can you avoid the inner loop?",
                  "When you're looking at x, which exact number would complete the pair?",
                  "Keep a dict from value to index for numbers you've already passed. Check for target - x before adding x."],
        "approach": ["Make an empty dict index_of.", "For each index i and value x: need = target - x.", "If need is in index_of, return [index_of[need], i].", "Otherwise store index_of[x] = i."],
        "solution": _code('''
            class Solution:
                def twoSum(self, nums: List[int], target: int) -> List[int]:
                    index_of = {}
                    for i, x in enumerate(nums):
                        need = target - x
                        if need in index_of:
                            return [index_of[need], i]
                        index_of[x] = i
        '''),
        "time": "O(n)", "space": "O(n)",
        "takeaway": "'Complement lookup': instead of searching for a partner, remember what you've seen and ask the map for the partner you need.",
    },
    {
        "id": "longest-common-prefix", "lc": 14, "title": "Longest Common Prefix", "slug": "longest-common-prefix",
        "pattern": "Arrays & Hashing",
        "statement": "Given a list of strings, return the longest starting piece that all of them share. If they share nothing, return an empty string.",
        "examples": [('strs = ["flight", "flow", "flower"]', '"fl"', "All three start with 'fl'; the third letters differ."),
                     ('strs = ["car", "dog"]', '""', "No shared first letter.")],
        "constraints": "1 <= len(strs) <= 200; each string has 0 to 200 lowercase letters",
        "hints": ["The answer can't be longer than the first string.",
                  "Start by guessing the whole first string is the prefix.",
                  "For each other string, shorten your guess one letter at a time until that string starts with it."],
        "approach": ["prefix = strs[0].", "For every other string s: while s doesn't start with prefix, chop the last letter off prefix.", "Return prefix (it may be empty)."],
        "solution": _code('''
            class Solution:
                def longestCommonPrefix(self, strs: List[str]) -> str:
                    prefix = strs[0]
                    for s in strs[1:]:
                        while not s.startswith(prefix):
                            prefix = prefix[:-1]
                    return prefix
        '''),
        "time": "O(total characters)", "space": "O(1) extra",
        "takeaway": "Start with the biggest possible answer and shrink it until it fits. The empty string always fits, so the loop always ends.",
    },
    # ── Two Pointers ────────────────────────────────────────────────────────
    {
        "id": "valid-palindrome", "lc": 125, "title": "Valid Palindrome", "slug": "valid-palindrome",
        "pattern": "Two Pointers",
        "statement": "A phrase is a palindrome if, after lowercasing it and removing everything that isn't a letter or digit, it reads the same forwards and backwards. Given a string s, return True if it's a palindrome.",
        "examples": [('s = "Was it a car or a cat I saw?"', "True", '"wasitacaroracatisaw" reads the same both ways.'),
                     ('s = "Not a palindrome"', "False", "")],
        "constraints": "1 <= len(s) <= 200,000; printable ASCII",
        "hints": ["You could build the cleaned-up string and compare it with its reverse. Can you avoid the extra copy?",
                  "Compare the first and last real characters, then move inward.",
                  "Use i from the left and j from the right. Skip characters that aren't letters or digits; compare lowercase versions."],
        "approach": ["i = 0, j = len(s) - 1.", "While i < j: skip non-alphanumeric characters on either side.", "If s[i].lower() != s[j].lower(), return False; else move both inward.", "Return True."],
        "solution": _code('''
            class Solution:
                def isPalindrome(self, s: str) -> bool:
                    i, j = 0, len(s) - 1
                    while i < j:
                        if not s[i].isalnum():
                            i += 1
                        elif not s[j].isalnum():
                            j -= 1
                        elif s[i].lower() != s[j].lower():
                            return False
                        else:
                            i += 1
                            j -= 1
                    return True
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Two pointers walking in from both ends check symmetry without building a new string.",
    },
    {
        "id": "reverse-string", "lc": 344, "title": "Reverse String", "slug": "reverse-string",
        "pattern": "Two Pointers",
        "statement": "Reverse a list of characters in place: change the list itself, using only O(1) extra memory. Return nothing.",
        "examples": [('s = ["c", "o", "d", "e"]', '["e", "d", "o", "c"]', "")],
        "constraints": "1 <= len(s) <= 100,000",
        "hints": ["You can't make a reversed copy. What can you do with just swaps?",
                  "The first and last characters trade places. Then what?",
                  "Swap s[i] and s[j], then move i right and j left, until they meet."],
        "approach": ["i = 0, j = len(s) - 1.", "While i < j: swap s[i] and s[j]; i += 1; j -= 1."],
        "solution": _code('''
            class Solution:
                def reverseString(self, s: List[str]) -> None:
                    i, j = 0, len(s) - 1
                    while i < j:
                        s[i], s[j] = s[j], s[i]
                        i += 1
                        j -= 1
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "In-place usually means swaps with two pointers.",
    },
    {
        "id": "move-zeroes", "lc": 283, "title": "Move Zeroes", "slug": "move-zeroes",
        "pattern": "Two Pointers",
        "statement": "Move every 0 in nums to the end, keeping the other numbers in their original order. Do it in place, without a copy of the list.",
        "examples": [("nums = [0, 5, 0, 3, 12]", "[5, 3, 12, 0, 0]", "")],
        "constraints": "1 <= len(nums) <= 10,000",
        "hints": ["Think of one pointer that reads every element and another that marks where the next non-zero should go.",
                  "Every time you read a non-zero, it belongs at the write position.",
                  "Swap nums[read] with nums[write] when nums[read] != 0, then move write forward."],
        "approach": ["write = 0.", "For read from 0 to the end: if nums[read] != 0, swap nums[read] and nums[write], then write += 1."],
        "solution": _code('''
            class Solution:
                def moveZeroes(self, nums: List[int]) -> None:
                    write = 0
                    for read in range(len(nums)):
                        if nums[read] != 0:
                            nums[write], nums[read] = nums[read], nums[write]
                            write += 1
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Read/write pointers: one scans, the other builds the answer at the front of the same array.",
    },
    {
        "id": "merge-sorted-array", "lc": 88, "title": "Merge Sorted Array", "slug": "merge-sorted-array",
        "pattern": "Two Pointers",
        "statement": "nums1 has room for m + n numbers: its first m are sorted, and the last n are zeros used as empty space. nums2 has n sorted numbers. Merge nums2 into nums1 so nums1 ends up fully sorted. Change nums1 in place.",
        "examples": [("nums1 = [2, 5, 9, 0, 0], m = 3, nums2 = [1, 6], n = 2", "nums1 = [1, 2, 5, 6, 9]", "")],
        "constraints": "0 <= m, n <= 200; len(nums1) == m + n",
        "hints": ["Merging from the front would overwrite numbers you still need.",
                  "Where is the free space? At the end. Which number goes in the very last slot?",
                  "Compare the largest remaining in each list and place the bigger one at the back, moving three pointers left."],
        "approach": ["i = m - 1, j = n - 1, k = m + n - 1.", "While j >= 0: if i >= 0 and nums1[i] > nums2[j], put nums1[i] at k and i -= 1; otherwise put nums2[j] at k and j -= 1. Then k -= 1.", "Anything left in nums1 is already in place."],
        "solution": _code('''
            class Solution:
                def merge(self, nums1: List[int], m: int, nums2: List[int], n: int) -> None:
                    i, j, k = m - 1, n - 1, m + n - 1
                    while j >= 0:
                        if i >= 0 and nums1[i] > nums2[j]:
                            nums1[k] = nums1[i]
                            i -= 1
                        else:
                            nums1[k] = nums2[j]
                            j -= 1
                        k -= 1
        '''),
        "time": "O(m + n)", "space": "O(1)",
        "takeaway": "When the free space is at the end, fill from the end.",
    },
    # ── Sliding Window ──────────────────────────────────────────────────────
    {
        "id": "best-time-to-buy-and-sell-stock", "lc": 121, "title": "Best Time to Buy and Sell Stock", "slug": "best-time-to-buy-and-sell-stock",
        "pattern": "Sliding Window",
        "statement": "prices[i] is a stock's price on day i. You may buy once and sell once on a later day. Return the most profit you can make, or 0 if you can't make any.",
        "examples": [("prices = [8, 3, 6, 1, 5, 4]", "4", "Buy at 1 (day 3), sell at 5 (day 4)."),
                     ("prices = [9, 7, 4, 2]", "0", "Prices only fall.")],
        "constraints": "1 <= len(prices) <= 100,000",
        "hints": ["For any sell day, which buy day is best?",
                  "The best buy day for today is the cheapest day so far.",
                  "Walk the prices once, tracking the lowest price seen and the best profit if you sold today."],
        "approach": ["lowest = infinity, best = 0.", "For each price p: lowest = min(lowest, p); best = max(best, p - lowest).", "Return best."],
        "solution": _code('''
            class Solution:
                def maxProfit(self, prices: List[int]) -> int:
                    lowest = float("inf")
                    best = 0
                    for p in prices:
                        lowest = min(lowest, p)
                        best = max(best, p - lowest)
                    return best
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "The window's left edge is the cheapest day so far; it only moves when you find a new low.",
    },
    {
        "id": "contains-duplicate-ii", "lc": 219, "title": "Contains Duplicate II", "slug": "contains-duplicate-ii",
        "pattern": "Sliding Window",
        "statement": "Given nums and an integer k, return True if two equal values sit at most k positions apart (indexes i != j with |i - j| <= k).",
        "examples": [("nums = [5, 1, 5, 2], k = 2", "True", "The 5s are at indexes 0 and 2, distance 2."),
                     ("nums = [5, 1, 2, 5], k = 2", "False", "The 5s are distance 3 apart.")],
        "constraints": "1 <= len(nums) <= 100,000; 0 <= k <= 100,000",
        "hints": ["You only care about the last k numbers before the current one.",
                  "Keep exactly those numbers in a set.",
                  "Before adding nums[i], check the set. After adding, if the set holds more than k numbers, remove nums[i - k]."],
        "approach": ["window = empty set.", "For each i: if nums[i] is in window, return True. Add it.", "If len(window) > k, remove nums[i - k].", "Return False."],
        "solution": _code('''
            class Solution:
                def containsNearbyDuplicate(self, nums: List[int], k: int) -> bool:
                    window = set()
                    for i, x in enumerate(nums):
                        if x in window:
                            return True
                        window.add(x)
                        if len(window) > k:
                            window.remove(nums[i - k])
                    return False
        '''),
        "time": "O(n)", "space": "O(k)",
        "takeaway": "A fixed-size window plus a set: add on the right, drop on the left.",
    },
    # ── Stack ───────────────────────────────────────────────────────────────
    {
        "id": "valid-parentheses", "lc": 20, "title": "Valid Parentheses", "slug": "valid-parentheses",
        "pattern": "Stack",
        "statement": "A string contains only ( ) [ ] { }. It's valid if every opening bracket is closed by the same type, in the right order. Return True if s is valid.",
        "examples": [('s = "{[()]}"', "True", ""), ('s = "([)]"', "False", "The ) closes before the [ is closed."), ('s = "(("', "False", "Never closed.")],
        "constraints": "1 <= len(s) <= 10,000",
        "hints": ["When you see a closing bracket, which opening bracket must it match?",
                  "The most recent unmatched opener. 'Most recent' is a stack.",
                  "Push openers. On a closer, the top of the stack must be its partner; pop it. At the end the stack must be empty."],
        "approach": ["pairs = {')': '(', ']': '[', '}': '{'}; stack = [].", "For each c: if it's a closer, the stack must be non-empty with pairs[c] on top; pop. Otherwise push c.", "Return True only if the stack is empty."],
        "solution": _code('''
            class Solution:
                def isValid(self, s: str) -> bool:
                    pairs = {")": "(", "]": "[", "}": "{"}
                    stack = []
                    for c in s:
                        if c in pairs:
                            if not stack or stack[-1] != pairs[c]:
                                return False
                            stack.pop()
                        else:
                            stack.append(c)
                    return not stack
        '''),
        "time": "O(n)", "space": "O(n)",
        "takeaway": "Nesting means 'last opened, first closed', which is exactly a stack.",
    },
    {
        "id": "implement-queue-using-stacks", "lc": 232, "title": "Implement Queue using Stacks", "slug": "implement-queue-using-stacks",
        "pattern": "Stack",
        "statement": "Build a first-in-first-out queue class MyQueue with push(x), pop(), peek() and empty(), using only stack operations (append, pop from the end, look at the end, length).",
        "examples": [("push(4), push(7), peek(), pop(), empty()", "4, 4, False", "4 went in first, so it comes out first.")],
        "constraints": "At most 100 calls; pop and peek are only called on a non-empty queue",
        "hints": ["A stack reverses order. What happens if you reverse twice?",
                  "Use two stacks: one for incoming items, one for outgoing.",
                  "Only move items from inbox to outbox when outbox is empty. Each item moves at most once."],
        "approach": ["push: append to inbox.", "pop/peek: if outbox is empty, pop everything from inbox onto outbox; then use outbox's top.", "empty: both stacks are empty."],
        "solution": _code('''
            class MyQueue:
                def __init__(self):
                    self.inbox = []
                    self.outbox = []

                def push(self, x: int) -> None:
                    self.inbox.append(x)

                def _shift(self) -> None:
                    if not self.outbox:
                        while self.inbox:
                            self.outbox.append(self.inbox.pop())

                def pop(self) -> int:
                    self._shift()
                    return self.outbox.pop()

                def peek(self) -> int:
                    self._shift()
                    return self.outbox[-1]

                def empty(self) -> bool:
                    return not self.inbox and not self.outbox
        '''),
        "time": "O(1) amortized per call", "space": "O(n)",
        "takeaway": "Two reversals restore the original order. 'Amortized' means the occasional big move is paid for by many cheap calls.",
    },
    {
        "id": "remove-all-adjacent-duplicates-in-string", "lc": 1047, "title": "Remove All Adjacent Duplicates In String", "slug": "remove-all-adjacent-duplicates-in-string",
        "pattern": "Stack",
        "statement": "Repeatedly delete two equal letters that sit next to each other, until no such pair is left. Return the final string.",
        "examples": [('s = "xyyxz"', '"z"', 'Remove "yy" to get "xxz", then remove "xx".'),
                     ('s = "aabccb"', '""', "Everything cancels out.")],
        "constraints": "1 <= len(s) <= 100,000; lowercase letters",
        "hints": ["After you delete a pair, the letters on either side become neighbors. Which earlier letter can a new letter cancel?",
                  "Only the most recent surviving letter.",
                  "Use a stack of surviving letters: if the new letter equals the top, pop; otherwise push."],
        "approach": ["stack = [].", "For each letter c: if stack and stack[-1] == c, pop; else push c.", "Return ''.join(stack)."],
        "solution": _code('''
            class Solution:
                def removeDuplicates(self, s: str) -> str:
                    stack = []
                    for c in s:
                        if stack and stack[-1] == c:
                            stack.pop()
                        else:
                            stack.append(c)
                    return "".join(stack)
        '''),
        "time": "O(n)", "space": "O(n)",
        "takeaway": "A stack lets you 'undo' the last thing as soon as something cancels it.",
    },
    # ── Binary Search ───────────────────────────────────────────────────────
    {
        "id": "binary-search", "lc": 704, "title": "Binary Search", "slug": "binary-search",
        "pattern": "Binary Search",
        "statement": "nums is sorted in increasing order with no repeats. Return the index of target, or -1 if it isn't there. Your solution must take O(log n) time.",
        "examples": [("nums = [-4, 0, 2, 7, 11], target = 7", "3", ""), ("nums = [-4, 0, 2, 7, 11], target = 5", "-1", "")],
        "constraints": "1 <= len(nums) <= 10,000",
        "hints": ["Look at the middle element. If it's too small, which half can you ignore?",
                  "Keep a range lo..hi that could still contain target.",
                  "While lo <= hi: mid = (lo + hi) // 2; move lo to mid + 1 or hi to mid - 1."],
        "approach": ["lo = 0, hi = len(nums) - 1.", "While lo <= hi: mid = (lo + hi) // 2. If nums[mid] == target return mid; if it's smaller, lo = mid + 1; else hi = mid - 1.", "Return -1."],
        "solution": _code('''
            class Solution:
                def search(self, nums: List[int], target: int) -> int:
                    lo, hi = 0, len(nums) - 1
                    while lo <= hi:
                        mid = (lo + hi) // 2
                        if nums[mid] == target:
                            return mid
                        if nums[mid] < target:
                            lo = mid + 1
                        else:
                            hi = mid - 1
                    return -1
        '''),
        "time": "O(log n)", "space": "O(1)",
        "takeaway": "Each step halves the search range. Be precise about whether hi is included (lo <= hi) or not.",
    },
    {
        "id": "search-insert-position", "lc": 35, "title": "Search Insert Position", "slug": "search-insert-position",
        "pattern": "Binary Search",
        "statement": "nums is sorted with no repeats. Return the index of target if it's there; otherwise return the index where it would go to keep nums sorted. Use O(log n) time.",
        "examples": [("nums = [2, 4, 8, 10], target = 8", "2", ""), ("nums = [2, 4, 8, 10], target = 5", "2", "5 goes between 4 and 8."), ("nums = [2, 4, 8, 10], target = 12", "4", "After everything.")],
        "constraints": "1 <= len(nums) <= 10,000",
        "hints": ["You're looking for the first index whose value is >= target.",
                  "Use a range lo..hi where hi can equal len(nums) (insert at the end).",
                  "While lo < hi: if nums[mid] < target, lo = mid + 1, else hi = mid. Return lo."],
        "approach": ["lo = 0, hi = len(nums).", "While lo < hi: mid = (lo + hi) // 2; if nums[mid] < target: lo = mid + 1 else hi = mid.", "Return lo."],
        "solution": _code('''
            class Solution:
                def searchInsert(self, nums: List[int], target: int) -> int:
                    lo, hi = 0, len(nums)
                    while lo < hi:
                        mid = (lo + hi) // 2
                        if nums[mid] < target:
                            lo = mid + 1
                        else:
                            hi = mid
                    return lo
        '''),
        "time": "O(log n)", "space": "O(1)",
        "takeaway": "'First position where the condition becomes true' is the most useful binary search template. Learn this one well.",
    },
    {
        "id": "first-bad-version", "lc": 278, "title": "First Bad Version", "slug": "first-bad-version",
        "pattern": "Binary Search",
        "statement": "Versions 1..n were released in order. Once a version is bad, every later one is bad too. A function isBadVersion(v) tells you if v is bad. Find the first bad version using as few calls as possible.",
        "examples": [("n = 6, first bad version is 4", "4", "isBadVersion(3) is False, isBadVersion(4) is True.")],
        "constraints": "1 <= first bad <= n <= 2^31 - 1",
        "hints": ["The answers look like False, False, ..., True, True. Where does it flip?",
                  "This is 'first position where the condition becomes true'.",
                  "lo = 1, hi = n. If mid is bad, the answer is mid or earlier (hi = mid); otherwise it's later (lo = mid + 1)."],
        "approach": ["lo = 1, hi = n.", "While lo < hi: mid = (lo + hi) // 2; if isBadVersion(mid): hi = mid else lo = mid + 1.", "Return lo."],
        "solution": _code('''
            class Solution:
                def firstBadVersion(self, n: int) -> int:
                    lo, hi = 1, n
                    while lo < hi:
                        mid = (lo + hi) // 2
                        if isBadVersion(mid):
                            hi = mid
                        else:
                            lo = mid + 1
                    return lo
        '''),
        "time": "O(log n) calls", "space": "O(1)",
        "takeaway": "Binary search works on any yes/no question that flips once, not only on sorted arrays.",
    },
    # ── Linked List ─────────────────────────────────────────────────────────
    {
        "id": "reverse-linked-list", "lc": 206, "title": "Reverse Linked List", "slug": "reverse-linked-list",
        "pattern": "Linked List",
        "statement": "Given the head of a singly linked list, reverse it and return the new head.",
        "examples": [("7 -> 3 -> 9", "9 -> 3 -> 7", ""), ("empty list", "empty list", "")],
        "constraints": "0 to 5,000 nodes",
        "hints": ["Draw three nodes as boxes. Which arrows need to flip?",
                  "As you walk the list, you need the previous node, the current node, and the next node.",
                  "Save nxt = cur.next, point cur.next at prev, then move prev and cur one step forward."],
        "approach": ["prev = None, cur = head.", "While cur: nxt = cur.next; cur.next = prev; prev = cur; cur = nxt.", "Return prev."],
        "solution": _code('''
            class Solution:
                def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    prev, cur = None, head
                    while cur:
                        nxt = cur.next
                        cur.next = prev
                        prev, cur = cur, nxt
                    return prev
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Save the next pointer before you overwrite it. This prev/cur/next dance shows up everywhere.",
    },
    {
        "id": "merge-two-sorted-lists", "lc": 21, "title": "Merge Two Sorted Lists", "slug": "merge-two-sorted-lists",
        "pattern": "Linked List",
        "statement": "You get the heads of two sorted linked lists. Splice their nodes together into one sorted list and return its head.",
        "examples": [("1 -> 4 -> 6 and 2 -> 3 -> 7", "1 -> 2 -> 3 -> 4 -> 6 -> 7", "")],
        "constraints": "0 to 50 nodes in each list",
        "hints": ["Which node comes first in the result? The smaller of the two heads.",
                  "Avoid special-casing the first node with a dummy node in front of the result.",
                  "Keep a tail pointer; attach the smaller current node, advance that list, and attach whatever is left at the end."],
        "approach": ["dummy = ListNode(); tail = dummy.", "While both lists have nodes: attach the smaller to tail.next, advance that list, tail = tail.next.", "tail.next = whichever list still has nodes.", "Return dummy.next."],
        "solution": _code('''
            class Solution:
                def mergeTwoLists(self, list1: Optional[ListNode], list2: Optional[ListNode]) -> Optional[ListNode]:
                    dummy = tail = ListNode()
                    while list1 and list2:
                        if list1.val <= list2.val:
                            tail.next, list1 = list1, list1.next
                        else:
                            tail.next, list2 = list2, list2.next
                        tail = tail.next
                    tail.next = list1 or list2
                    return dummy.next
        '''),
        "time": "O(n + m)", "space": "O(1)",
        "takeaway": "A dummy head node removes the 'is this the first node?' special case.",
    },
    {
        "id": "linked-list-cycle", "lc": 141, "title": "Linked List Cycle", "slug": "linked-list-cycle",
        "pattern": "Linked List",
        "statement": "Return True if a linked list has a cycle (following next pointers eventually revisits a node), or False if it ends.",
        "examples": [("3 -> 8 -> 5 -> 2, and 2 points back to 8", "True", ""), ("3 -> 8", "False", "")],
        "constraints": "0 to 10,000 nodes; aim for O(1) memory",
        "hints": ["A set of visited nodes works, but uses O(n) memory.",
                  "Picture two runners on a circular track at different speeds.",
                  "Move slow one step and fast two steps. If they ever meet, there's a cycle; if fast reaches the end, there isn't."],
        "approach": ["slow = fast = head.", "While fast and fast.next: slow = slow.next; fast = fast.next.next; if slow is fast, return True.", "Return False."],
        "solution": _code('''
            class Solution:
                def hasCycle(self, head: Optional[ListNode]) -> bool:
                    slow = fast = head
                    while fast and fast.next:
                        slow = slow.next
                        fast = fast.next.next
                        if slow is fast:
                            return True
                    return False
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Floyd's slow/fast pointers: inside a loop the fast one gains one step each turn, so it must catch up.",
    },
    {
        "id": "middle-of-the-linked-list", "lc": 876, "title": "Middle of the Linked List", "slug": "middle-of-the-linked-list",
        "pattern": "Linked List",
        "statement": "Return the middle node of a linked list. If there are two middle nodes, return the second one.",
        "examples": [("10 -> 20 -> 30 -> 40 -> 50", "the node with 30", ""), ("10 -> 20 -> 30 -> 40 -> 50 -> 60", "the node with 40", "Two middles (30, 40): take the second.")],
        "constraints": "1 to 100 nodes",
        "hints": ["You could count the nodes, then walk half way. Can you do it in one pass?",
                  "If one pointer moves twice as fast as another...",
                  "When fast reaches the end, slow is at the middle."],
        "approach": ["slow = fast = head.", "While fast and fast.next: slow = slow.next; fast = fast.next.next.", "Return slow."],
        "solution": _code('''
            class Solution:
                def middleNode(self, head: Optional[ListNode]) -> Optional[ListNode]:
                    slow = fast = head
                    while fast and fast.next:
                        slow = slow.next
                        fast = fast.next.next
                    return slow
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Same slow/fast trick as cycle detection. The stopping condition decides which middle you get.",
    },
    # ── Trees ───────────────────────────────────────────────────────────────
    {
        "id": "maximum-depth-of-binary-tree", "lc": 104, "title": "Maximum Depth of Binary Tree", "slug": "maximum-depth-of-binary-tree",
        "pattern": "Trees",
        "statement": "Return the number of nodes on the longest path from the root down to a leaf.",
        "examples": [("root = [5, 3, 8, null, null, 7, 9]  (5 has children 3 and 8; 8 has children 7 and 9)", "3", "5 -> 8 -> 7.")],
        "constraints": "0 to 10,000 nodes",
        "hints": ["If you knew the depth of the left and right subtrees, what's the depth of the whole tree?",
                  "What's the depth of an empty tree?",
                  "depth(node) = 1 + max(depth(left), depth(right)), and depth(None) = 0."],
        "approach": ["If root is None, return 0.", "Return 1 + max(maxDepth(root.left), maxDepth(root.right))."],
        "solution": _code('''
            class Solution:
                def maxDepth(self, root: Optional[TreeNode]) -> int:
                    if not root:
                        return 0
                    return 1 + max(self.maxDepth(root.left), self.maxDepth(root.right))
        '''),
        "time": "O(n)", "space": "O(h), h = tree height (the recursion stack)",
        "takeaway": "The base case (empty tree) plus 'combine the two children' solves most tree problems.",
    },
    {
        "id": "invert-binary-tree", "lc": 226, "title": "Invert Binary Tree", "slug": "invert-binary-tree",
        "pattern": "Trees",
        "statement": "Mirror a binary tree: every node's left and right children swap places, all the way down. Return the root.",
        "examples": [("root = [5, 3, 8, 1, 4]", "[5, 8, 3, null, null, 4, 1]", "3 and 8 swap, and 3's children 1 and 4 swap.")],
        "constraints": "0 to 100 nodes",
        "hints": ["What has to happen at a single node?",
                  "Swap its two children, and then the subtrees still need to be mirrored too.",
                  "Recursively invert both subtrees, then swap them."],
        "approach": ["If root is None, return None.", "root.left, root.right = invert(root.right), invert(root.left).", "Return root."],
        "solution": _code('''
            class Solution:
                def invertTree(self, root: Optional[TreeNode]) -> Optional[TreeNode]:
                    if root:
                        root.left, root.right = self.invertTree(root.right), self.invertTree(root.left)
                    return root
        '''),
        "time": "O(n)", "space": "O(h)",
        "takeaway": "Do the same small job at every node and let recursion handle the rest.",
    },
    {
        "id": "same-tree", "lc": 100, "title": "Same Tree", "slug": "same-tree",
        "pattern": "Trees",
        "statement": "Return True if two binary trees have the same shape and the same value at every node.",
        "examples": [("p = [1, 2, 3], q = [1, 2, 3]", "True", ""), ("p = [1, 2], q = [1, null, 2]", "False", "The 2 is a left child in p but a right child in q.")],
        "constraints": "0 to 100 nodes in each tree",
        "hints": ["Two empty trees are the same. One empty and one not?",
                  "If both roots exist, what must be true about their values and their subtrees?",
                  "same(p, q) = p.val == q.val and same(p.left, q.left) and same(p.right, q.right)."],
        "approach": ["If both are None: True. If only one is None: False.", "Return p.val == q.val and same(left subtrees) and same(right subtrees)."],
        "solution": _code('''
            class Solution:
                def isSameTree(self, p: Optional[TreeNode], q: Optional[TreeNode]) -> bool:
                    if not p and not q:
                        return True
                    if not p or not q:
                        return False
                    return p.val == q.val and self.isSameTree(p.left, q.left) and self.isSameTree(p.right, q.right)
        '''),
        "time": "O(n)", "space": "O(h)",
        "takeaway": "Handle the None cases first; then the recursive case can safely read .val.",
    },
    {
        "id": "balanced-binary-tree", "lc": 110, "title": "Balanced Binary Tree", "slug": "balanced-binary-tree",
        "pattern": "Trees",
        "statement": "A tree is balanced if, at every node, the heights of the left and right subtrees differ by at most 1. Return True if the tree is balanced.",
        "examples": [("root = [5, 3, 8, null, null, 7, 9]", "True", ""), ("root = [1, 2, null, 3, null, 4]  (a chain going left)", "False", "At the root, left height is 3 and right height is 0.")],
        "constraints": "0 to 5,000 nodes",
        "hints": ["Computing height separately at every node is O(n^2). Can one pass do both jobs?",
                  "Have your helper return the height, or a special value meaning 'already unbalanced'.",
                  "Return -1 for unbalanced. If either child returns -1 or their heights differ by more than 1, return -1."],
        "approach": ["height(node): None -> 0.", "l = height(left), r = height(right). If l == -1 or r == -1 or |l - r| > 1, return -1.", "Otherwise return 1 + max(l, r).", "Balanced if height(root) != -1."],
        "solution": _code('''
            class Solution:
                def isBalanced(self, root: Optional[TreeNode]) -> bool:
                    def height(node):
                        if not node:
                            return 0
                        l, r = height(node.left), height(node.right)
                        if l == -1 or r == -1 or abs(l - r) > 1:
                            return -1
                        return 1 + max(l, r)
                    return height(root) != -1
        '''),
        "time": "O(n)", "space": "O(h)",
        "takeaway": "Return extra information up the tree (here, a height that doubles as an error flag) so you visit each node once.",
    },
    {
        "id": "diameter-of-binary-tree", "lc": 543, "title": "Diameter of Binary Tree", "slug": "diameter-of-binary-tree",
        "pattern": "Trees",
        "statement": "The diameter is the number of edges on the longest path between any two nodes. The path doesn't have to pass through the root. Return the diameter.",
        "examples": [("root = [6, 2, 9, 1, 4]  (6 has children 2 and 9; 2 has children 1 and 4)", "3", "1 -> 2 -> 6 -> 9 has 3 edges.")],
        "constraints": "1 to 10,000 nodes",
        "hints": ["Every path has a highest node where it 'bends'. How long is the longest path bending at a given node?",
                  "Left depth + right depth.",
                  "Write depth(node) that returns the height, and update a best variable with left + right at every node."],
        "approach": ["best = 0.", "depth(node): None -> 0; l, r = depth(left), depth(right); best = max(best, l + r); return 1 + max(l, r).", "Call depth(root), return best."],
        "solution": _code('''
            class Solution:
                def diameterOfBinaryTree(self, root: Optional[TreeNode]) -> int:
                    best = 0
                    def depth(node):
                        nonlocal best
                        if not node:
                            return 0
                        l, r = depth(node.left), depth(node.right)
                        best = max(best, l + r)
                        return 1 + max(l, r)
                    depth(root)
                    return best
        '''),
        "time": "O(n)", "space": "O(h)",
        "takeaway": "Sometimes the helper returns one thing (height) while you track the real answer (diameter) on the side.",
    },
    # ── Heap / Priority Queue ───────────────────────────────────────────────
    {
        "id": "last-stone-weight", "lc": 1046, "title": "Last Stone Weight", "slug": "last-stone-weight",
        "pattern": "Heap / Priority Queue",
        "statement": "Each turn, smash the two heaviest stones (weights x <= y). If x == y both are destroyed; otherwise one stone of weight y - x remains. Return the weight of the last stone, or 0 if none are left.",
        "examples": [("stones = [3, 5, 8, 2]", "2", "8 and 5 -> 3, leaving [3, 3, 2]; 3 and 3 cancel, leaving [2]."), ("stones = [4, 4]", "0", "")],
        "constraints": "1 <= len(stones) <= 30",
        "hints": ["Sorting every turn works but repeats a lot of work.",
                  "You need 'the biggest item' over and over: that's a max-heap.",
                  "Python's heapq is a min-heap, so store negative weights."],
        "approach": ["heap = [-w for w in stones]; heapify it.", "While more than one stone: pop y and x (the two largest); if they differ, push -(y - x).", "Return -heap[0] if a stone is left, else 0."],
        "solution": _code('''
            class Solution:
                def lastStoneWeight(self, stones: List[int]) -> int:
                    heap = [-w for w in stones]
                    heapq.heapify(heap)
                    while len(heap) > 1:
                        y = -heapq.heappop(heap)
                        x = -heapq.heappop(heap)
                        if y != x:
                            heapq.heappush(heap, -(y - x))
                    return -heap[0] if heap else 0
        '''),
        "time": "O(n log n)", "space": "O(n)",
        "takeaway": "heapq is a min-heap; negate values to get a max-heap.",
    },
    # ── Graphs ──────────────────────────────────────────────────────────────
    {
        "id": "flood-fill", "lc": 733, "title": "Flood Fill", "slug": "flood-fill",
        "pattern": "Graphs",
        "statement": "image is a grid of colors. Starting at (sr, sc), recolor that cell and every cell connected to it (up/down/left/right) that has the same starting color. Return the grid, like a paint-bucket tool.",
        "examples": [("image = [[1,1,0],[1,0,0],[1,1,1]], sr = 0, sc = 0, color = 2", "[[2,2,0],[2,0,0],[2,2,2]]", "All the 1s are connected to the top-left cell.")],
        "constraints": "Grid up to 50 x 50",
        "hints": ["Which neighbors should change? Only ones with the original color.",
                  "Visit cells with DFS or BFS from the start cell.",
                  "Careful: if the new color equals the old color, return right away, or you'll loop forever."],
        "approach": ["old = image[sr][sc]; if old == color, return image.", "Use a stack starting with (sr, sc). Pop a cell; if it's in bounds and has color old, paint it and push its 4 neighbors.", "Return image."],
        "solution": _code('''
            class Solution:
                def floodFill(self, image: List[List[int]], sr: int, sc: int, color: int) -> List[List[int]]:
                    old = image[sr][sc]
                    if old == color:
                        return image
                    stack = [(sr, sc)]
                    while stack:
                        r, c = stack.pop()
                        if 0 <= r < len(image) and 0 <= c < len(image[0]) and image[r][c] == old:
                            image[r][c] = color
                            stack += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
                    return image
        '''),
        "time": "O(rows x cols)", "space": "O(rows x cols)",
        "takeaway": "Painting a cell is how you mark it visited. Always ask how you avoid revisiting.",
    },
    # ── 1-D Dynamic Programming ─────────────────────────────────────────────
    {
        "id": "climbing-stairs", "lc": 70, "title": "Climbing Stairs", "slug": "climbing-stairs",
        "pattern": "1-D Dynamic Programming",
        "statement": "A staircase has n steps. Each move climbs 1 or 2 steps. How many different ways can you reach the top?",
        "examples": [("n = 4", "5", "1+1+1+1, 1+1+2, 1+2+1, 2+1+1, 2+2."), ("n = 1", "1", "")],
        "constraints": "1 <= n <= 45",
        "hints": ["Think about your very last move: it was either 1 step or 2 steps.",
                  "So ways(n) = ways(n - 1) + ways(n - 2). What are the base cases?",
                  "Build from the bottom with two variables instead of recursion."],
        "approach": ["a, b = 1, 1 (ways to reach step 0 and step 1).", "Repeat n - 1 times: a, b = b, a + b.", "Return b."],
        "solution": _code('''
            class Solution:
                def climbStairs(self, n: int) -> int:
                    a, b = 1, 1
                    for _ in range(n - 1):
                        a, b = b, a + b
                    return b
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "'How many ways' + 'last move was one of a few options' = add up the smaller answers. It's Fibonacci.",
    },
    {
        "id": "min-cost-climbing-stairs", "lc": 746, "title": "Min Cost Climbing Stairs", "slug": "min-cost-climbing-stairs",
        "pattern": "1-D Dynamic Programming",
        "statement": "cost[i] is what you pay to stand on step i. You can start on step 0 or step 1, and each move climbs 1 or 2 steps. Return the cheapest total cost to get past the last step.",
        "examples": [("cost = [5, 10, 3, 8]", "8", "Start on step 0 (5), jump to step 2 (3), jump past the end.")],
        "constraints": "2 <= len(cost) <= 1,000",
        "hints": ["What's the cheapest way to stand on step i?",
                  "You arrived from step i - 1 or i - 2, so best(i) = cost[i] + min(best(i - 1), best(i - 2)).",
                  "The top can be reached from either of the last two steps."],
        "approach": ["a, b = cost[0], cost[1] (cheapest to stand on steps 0 and 1).", "For i from 2: a, b = b, cost[i] + min(a, b).", "Return min(a, b)."],
        "solution": _code('''
            class Solution:
                def minCostClimbingStairs(self, cost: List[int]) -> int:
                    a, b = cost[0], cost[1]
                    for i in range(2, len(cost)):
                        a, b = b, cost[i] + min(a, b)
                    return min(a, b)
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Same shape as Climbing Stairs, but with min instead of +. Define exactly what each value means before coding.",
    },
    # ── Bit Manipulation ────────────────────────────────────────────────────
    {
        "id": "single-number", "lc": 136, "title": "Single Number", "slug": "single-number",
        "pattern": "Bit Manipulation",
        "statement": "Every number in nums appears exactly twice except one, which appears once. Find it in O(n) time and O(1) extra memory.",
        "examples": [("nums = [7, 3, 7]", "3", ""), ("nums = [2, 9, 4, 9, 2]", "4", "")],
        "constraints": "1 <= len(nums) <= 30,000",
        "hints": ["A set would work but uses O(n) memory.",
                  "Is there an operation where a number combined with itself disappears?",
                  "XOR: x ^ x = 0 and x ^ 0 = x, and order doesn't matter. XOR everything together."],
        "approach": ["result = 0.", "For each x: result ^= x.", "Return result."],
        "solution": _code('''
            class Solution:
                def singleNumber(self, nums: List[int]) -> int:
                    result = 0
                    for x in nums:
                        result ^= x
                    return result
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "XOR cancels pairs. Remember it whenever things 'come in pairs except one'.",
    },
    {
        "id": "missing-number", "lc": 268, "title": "Missing Number", "slug": "missing-number",
        "pattern": "Bit Manipulation",
        "statement": "nums holds n different numbers taken from 0, 1, ..., n. Exactly one number in that range is missing. Return it.",
        "examples": [("nums = [4, 2, 0, 1]", "3", "n = 4, so the range is 0..4."), ("nums = [1]", "0", "n = 1, range 0..1.")],
        "constraints": "1 <= n <= 10,000",
        "hints": ["What would the numbers 0..n add up to if none were missing?",
                  "0 + 1 + ... + n = n(n + 1) / 2.",
                  "The missing number is that total minus sum(nums). (XOR of all indexes and values also works.)"],
        "approach": ["n = len(nums).", "Return n * (n + 1) // 2 - sum(nums)."],
        "solution": _code('''
            class Solution:
                def missingNumber(self, nums: List[int]) -> int:
                    n = len(nums)
                    return n * (n + 1) // 2 - sum(nums)
        '''),
        "time": "O(n)", "space": "O(1)",
        "takeaway": "Compare against what a complete set would look like. The difference is your answer.",
    },
]

LEVELS = {"easy": EASY}
