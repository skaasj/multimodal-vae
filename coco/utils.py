"""Random helper variables and utilities."""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import torch
import random
from glove import GloVe
from nltk.tokenize import word_tokenize

MAX_WORDS = 100  # max number of words in a sentence
SOS = '<s>'
EOS = '</s>'
MAX_WORDS += 2


def text_transformer(deterministic=False):
    """Returns a function that should be used as a transformer
    in DataLoader for COCO captions.

    :param deterministic: COCO has 5 captions for each image.
                          if True, always take the 1st caption.
                          if False, randomly choose a caption.
    :return transform_text: function that takes a tuple of five 
                            strings as input
    """
    glove = GloVe()

    def transform_text(five_sentences):
        if deterministic:
            sentence = five_sentences[0]
        else:
            sentence = random.choice(five_sentences)

        words = word_tokenize(sentence)
        if len(words) > MAX_WORDS:
            words = words[:MAX_WORDS]
        words = [SOS] + words + [EOS]

        embeddings = torch.zeros((MAX_WORDS, 300))
        for i, word in enumerate(words):
            glove_vec = glove.get_word(word)
            if glove_vec is not None:
                embeddings[i] = glove_vec

        return embeddings

    return transform_text
