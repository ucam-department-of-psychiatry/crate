#!/usr/bin/env python

"""
crate_anon/common/bugfix_flashtext.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

THIS FILE, however, is by another author: from
https://github.com/vi3k6i5/flashtext/issues/44, by Ihor Bobak; added to
Flashtext code; licensed under the MIT License as per
https://github.com/vi3k6i5/flashtext/blob/master/LICENSE.

Rationale:

There is currently a bug in the method :meth:`replace_keywords` in the external
module ``flashtext`` in which certain characters provoke an 'index out of
range' error when working in case-insensitive mode. This is because some
non-ascii characters are larger in their lower-case form. Thanks to Ihor Bobak
for this bugfix.

Edits for PyCharm linter.
"""

from flashtext import KeywordProcessor


# noinspection PyAbstractClass
class KeywordProcessorFixed(KeywordProcessor):
    # noinspection PyUnusedLocal
    def replace_keywords(self, a_sentence: str) -> str:
        if not a_sentence:
            # if sentence is empty or none just return the same.
            return a_sentence
        new_sentence = []

        if not self.case_sensitive:
            sentence = a_sentence.lower()
            # by Ihor Bobak:
            # some letters can expand in size when lower() is called, therefore we will preprocess  # noqa
            # a_sentense to find those letters which lower()-ed to 2 or more symbols.  # noqa
            # So, imagine that X is lowered as yz,  the rest are lowered as is:  A->a, B->b, C->c  # noqa
            # then for the string ABCXABC we want to get
            # ['A', 'B', 'C', 'X', '',  'A', 'B', 'C'] which corresponds to
            # ['a', 'b', 'c', 'y', 'z', 'a', 'b', 'c'] because when the code below will run by the indexes  # noqa
            # of the lowered string, it will "glue" the original string also by THE SAME indexes  # noqa
            orig_sentence = []
            for i in range(0, len(a_sentence)):
                char = a_sentence[i]
                len_char_lower = len(char.lower())
                for j in range(0, len_char_lower):  # in most cases it will work just one iteration and will add the same char  # noqa
                    orig_sentence.append(char if j == 0 else '')  # but if it happens that X->yz, then for z it will add ''  # noqa
        else:
            sentence = a_sentence
            orig_sentence = a_sentence

        current_word = ''
        current_dict = self.keyword_trie_dict
        current_white_space = ''
        sequence_end_pos = 0
        idx = 0
        sentence_len = len(sentence)
        while idx < sentence_len:
            char = sentence[idx]
            current_word += orig_sentence[idx]
            # when we reach whitespace
            if char not in self.non_word_boundaries:
                current_white_space = char
                # if end is present in current_dict
                if self._keyword in current_dict or char in current_dict:
                    # update longest sequence found
                    sequence_found = None
                    longest_sequence_found = None
                    is_longer_seq_found = False
                    if self._keyword in current_dict:
                        sequence_found = current_dict[self._keyword]
                        longest_sequence_found = current_dict[self._keyword]
                        sequence_end_pos = idx

                    # re look for longest_sequence from this position
                    if char in current_dict:
                        current_dict_continued = current_dict[char]
                        current_word_continued = current_word
                        idy = idx + 1
                        while idy < sentence_len:
                            inner_char = sentence[idy]
                            current_word_continued += orig_sentence[idy]
                            if inner_char not in self.non_word_boundaries and self._keyword in current_dict_continued:  # noqa
                                # update longest sequence found
                                current_white_space = inner_char
                                longest_sequence_found = current_dict_continued[self._keyword]  # noqa
                                sequence_end_pos = idy
                                is_longer_seq_found = True
                            if inner_char in current_dict_continued:
                                current_dict_continued = current_dict_continued[inner_char]  # noqa
                            else:
                                break
                            idy += 1
                        else:
                            # end of sentence reached.
                            if self._keyword in current_dict_continued:
                                # update longest sequence found
                                current_white_space = ''
                                longest_sequence_found = current_dict_continued[self._keyword]  # noqa
                                sequence_end_pos = idy
                                is_longer_seq_found = True
                        if is_longer_seq_found:
                            idx = sequence_end_pos
                            current_word = current_word_continued
                    current_dict = self.keyword_trie_dict
                    if longest_sequence_found:
                        new_sentence.append(longest_sequence_found)
                        new_sentence.append(current_white_space)
                        current_word = ''
                        current_white_space = ''
                    else:
                        new_sentence.append(current_word)
                        current_word = ''
                        current_white_space = ''
                else:
                    # we reset current_dict
                    current_dict = self.keyword_trie_dict
                    new_sentence.append(current_word)
                    current_word = ''
                    current_white_space = ''
            elif char in current_dict:
                # we can continue from this char
                current_dict = current_dict[char]
            else:
                # we reset current_dict
                current_dict = self.keyword_trie_dict
                # skip to end of word
                idy = idx + 1
                while idy < sentence_len:
                    char = sentence[idy]
                    current_word += orig_sentence[idy]
                    if char not in self.non_word_boundaries:
                        break
                    idy += 1
                idx = idy
                new_sentence.append(current_word)
                current_word = ''
                current_white_space = ''
            # if we are end of sentence and have a sequence discovered
            if idx + 1 >= sentence_len:
                if self._keyword in current_dict:
                    sequence_found = current_dict[self._keyword]
                    new_sentence.append(sequence_found)
                else:
                    new_sentence.append(current_word)
            idx += 1
        return "".join(new_sentence)

