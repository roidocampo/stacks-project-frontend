#!/usr/bin/env python

from os.path import dirname, realpath, join
import sys

script_dir = dirname(realpath(__file__))
stacks_dir = join(script_dir, "stacks-project")
sys.path.append(join(stacks_dir, "scripts"))

import functions

chapters = functions.list_text_files(join(stacks_dir, ""))
label_types = functions.list_of_standard_labels
tags = functions.get_tags(join(stacks_dir, ""))

_label_of_tag = dict(tags)
_tag_of_label = dict((l,t) for (t,l) in tags)

def tag2label(tag):
    return _label_of_tag[tag]

def label2tag(label):
    return _tag_of_label[label]

def chapter_number(name):
    return chapters.index(name)+1
