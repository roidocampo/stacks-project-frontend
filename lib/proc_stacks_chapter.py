#!/usr/bin/env python

from __future__ import print_function

import collections
import glob
import json
import os
import shutil
import sys

try:
    import regex as re
except ImportError:
    import re

import stacks_project_info
import katexfilter

#######################################################################
# 
#######################################################################

PROJECT_DIR = os.path.dirname(
              os.path.dirname(
              os.path.realpath(
                  __file__
              )))

STACKS_DIR = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                "stacks-project"
                )

#######################################################################
# 
#######################################################################

class TagCacheClass(object):

    def __init__(self):
        self.tags = {}
        self.tag_children = collections.defaultdict(list)
        self.chapter_divisions = collections.defaultdict(lambda:1)
        self.tag_cache_file = os.path.join(PROJECT_DIR, "web", "tag_cache.json")
        self._number2tag = collections.defaultdict(lambda:"undefined")

    def save(self):
        obj = dict(
            tags=self.tags, 
            chapter_divisions=self.chapter_divisions,
            tag_children=self.tag_children
        )
        with open(self.tag_cache_file, "w") as tag_cache_file_obj:
            json.dump(obj, tag_cache_file_obj, indent=4)

    def load(self):
        if os.path.exists(self.tag_cache_file):
            with open(self.tag_cache_file, "r") as tag_cache_file_obj:
                obj = json.load(tag_cache_file_obj)
            self.tags.clear()
            self.tags.update(obj.tags)
            self.chapter_divisions.clear()
            self.chapter_divisions.update(obj.chapter_divisions)
            self.tag_children.clear()
            self.tag_children.update(obj.tag_children)

    def __setitem__(self, tag, value):
        number, chapter, division, title = value
        self.tags[tag] = value
        self._number2tag[number] = tag
        numbers = str(number).rsplit(".", 1)
        if len(numbers)>1:
            parent = self._number2tag[numbers[0]]
            self.tag_children[parent].append(tag)
        if self.chapter_divisions[chapter] < division:
            self.chapter_divisions[chapter] = division

    def __getitem__(self, tag):
        return self.tags[tag]

tag_cache = TagCacheClass()

#######################################################################
# Parser Object
#######################################################################

class Parser(object):

    regex = []
    rules = {}

    header_file_name = os.path.join(PROJECT_DIR, "static", "_header.html")
    footer_file_name = os.path.join(PROJECT_DIR, "static", "_footer.html")

    def __init__(self, chapter_name):
        self.chapter_name = chapter_name
        self.chapter_number = stacks_project_info.chapter_number(chapter_name)
        self.chapter_title = "Chapter {}".format(self.chapter_number)
        self.phase = "start"
        self.section_number = 0
        self.subsection_number = 0
        self.equation_number = 0
        self.item_number = 0
        self.footnote_number = 0
        self.division_start = 0
        self.division_number = 0 
        self.chapter_tag = self.format_with_tag(
            "{tag}\x01{tagdiv}", "section-phantom", 
            str(self.chapter_number), self.chapter_title)
        self.chapter_tag, self.chapter_tagdiv = self.chapter_tag.split("\x01")
        self.division_number = 1 
        self.division_first_section = { 0:0, 1:1 }
        self.division_last_section = { 0:0 }
        self.current_match = None
        self.math_mode = False
        self.bracket_level = 0
        self.bracket_actions = {}
        self.in_file_name = os.path.join(
                                STACKS_DIR,
                                chapter_name + ".tex"
                            )
        self.out_file_tmpl = os.path.join(
                                PROJECT_DIR,
                                "web",
                                chapter_name + "-{:0>3}.html"
                             )

    def _parse_handler(self, match):
        self.current_match = match
        key = match.lastgroup
        rule = self.rules[key]
        groups = match.groups()
        groups = [ g for g in groups if g is not None ]
        groups = groups[1:]
        output = rule(self, *groups)
        self.current_match = None
        if output is None:
            return ""
        else:
            return output

    def parse(self, string=None):
        if string is not None:
            tex_code = string
            return self.regex.sub(self._parse_handler, tex_code)
        else:
            with open(self.in_file_name, "r") as in_file:
                tex_code = in_file.read()
            tex_code = self._preparse(tex_code)
            html_code = self.regex.sub(self._parse_handler, tex_code)
            html_code = self._postparse(html_code)
            self.bodies = html_code.split("\x02")
            toc = self.create_toc()
            self.bodies.insert(0, toc)

    def _preparse(self, tex_code):
        title_match = re.search(r"\\title{(.*)}", tex_code)
        if title_match:
            self.chapter_title = title_match.group(1)
            self.chapter_title = self.parse(self.chapter_title)
            tag_cache.tags[self.chapter_tag][-1] = self.chapter_title
        start = re.search(r"\\label\{section-phantom\}", tex_code)
        if start:
            tex_code = tex_code[start.end():]
        end = re.search(r"\\input\{chapters\}", tex_code)
        if end:
            tex_code = tex_code[:end.start()]
        return tex_code

    def _postparse(self, html_code):
        def proc_katex(match):
            mode = match.group(1)
            tex_code = match.group(2)
            katex = katexfilter.process(tex_code)
            status = katex[0]
            katex = katex[1:]
            if status == "1":
                return katex
            elif mode == "normal":
                return "$" + tex_code + "$"
            else:
                return "$$" + tex_code + "$$"
        return re.sub(
            "\x04(.*?)\x05(.*?)\x06", 
            proc_katex, 
            html_code,
            flags=re.DOTALL)

    def create_toc(self):
        toc = ("<div class='toc'>\n" +
               "<h2>Table of contents</h2>\n" +
               "<ul>\n")
        for sect_tag in tag_cache.tag_children[self.chapter_tag]:
            number, chapter, division, title = tag_cache[sect_tag]
            file = "{}-{:0>3}.html".format(chapter, division)
            toc += "<li>"
            toc += "<a class='toc-num' href='{}#{}'>".format(file, sect_tag)
            toc += "&sect;" + number + "</a> "
            toc += "<a class='toc-title' href='{}#{}'>".format(file, sect_tag)
            toc += title + "</a>"
            toc += "\n"
        toc += "</ul>\n"
        toc += "</div>\n"
        return toc

    def _fix_tag_links(self, chapter, division, body):
        def aux_fix_tag_links(match):
            mode = match.group(1)
            tag = match.group(2)
            try:
                label_number, label_chapter, label_division, _ = tag_cache[tag]
            except:
                return "[" + tag + "]"
            if self.chapter_name == label_chapter and division == label_division:
                root = ""
            else:
                root = "{}-{:0>3}.html".format(label_chapter, label_division)
            if mode == "a":
                tmpl = "<a class='ref' href='{root}#{tag}'>{num}</a>"
            else:
                tmpl = "{num}"
            if match.group(3) is not None:
                label_number = match.group(3)
            return tmpl.format(root=root, tag=tag, num=label_number)
        return re.sub("\x01(.)(....)(?:\x03([^\x03]*)\x03)?", aux_fix_tag_links, body)


    def _write_html_file(self, out_file_name, body, nxt, prv, hme, div):
        title = self.chapter_title
        with open(out_file_name, "w") as out_file:
            with open(self.header_file_name,"r") as header_file:
                shutil.copyfileobj(header_file, out_file)
            if body and body[-1]!="\n":
                body += "\n"
            tmpl = "<div class='chapter' id='{tag}'>{tagdiv}\n"
            tmpl += "<div id='nav'>"
            tmpl += "<a id='nav-next' {nxt}></a>"
            tmpl += "<a id='nav-index' {hme}></a>"
            tmpl += "<a id='nav-prev' {prv}></a>"
            tmpl += "</div>\n"
            tmpl += "<div class='pre-title'>Chapter {num}</div>\n"
            tmpl += "<h1>{title}</h1>\n"
            if div != 0:
                tmpl += "<div class='post-title'>"
                tmpl += "Sections &sect;{num}.{s0} to &sect;{num}.{s1}"
                tmpl += "</div>\n"
            tmpl += "{body}"
            tmpl += "</div>"
            print(tmpl.format(
                    tag=self.chapter_tag, tagdiv=self.chapter_tagdiv,
                    title=title, body=body, hme=hme, nxt=nxt, prv=prv,
                    num=self.chapter_number, 
                    s0=self.division_first_section[div], 
                    s1=self.division_last_section[div],
                ), file=out_file)
            with open(self.footer_file_name,"r") as footer_file:
                shutil.copyfileobj(footer_file, out_file)

    def _get_next_prev_home(self, chapter, division):
        if division == tag_cache.chapter_divisions[chapter]:
            try:
                next_chapter = stacks_project_info.chapters[self.chapter_number]
            except:
                next_link = "class='disabled'"
            else:
                next_link = "href='{}-{:0>3}.html'".format(next_chapter, 0)
        else:
            next_link = "href='{}-{:0>3}.html'".format(chapter, division+1)
        if division == 0:
            if self.chapter_number == 1:
                prev_link = "class='disabled'"
            else:
                prev_chapter = stacks_project_info.chapters[self.chapter_number-2]
                prev_division = tag_cache.chapter_divisions[prev_chapter]
                prev_link = "href='{}-{:0>3}.html'".format(prev_chapter, prev_division)
        else:
            prev_link = "href='{}-{:0>3}.html'".format(chapter, division-1)
        home_link = "href='index.html'"
        return next_link, prev_link, home_link

    def write_files(self):
        for old_file in glob.iglob(self.out_file_tmpl.format("???")):
            os.remove(old_file)
        for division, body in enumerate(self.bodies):
            if division > 0:
                body = self._fix_tag_links(self.chapter_name, division, body)
            out_file_name = self.out_file_tmpl.format(division)
            nxt, prv, hme = self._get_next_prev_home(self.chapter_name, division)
            self._write_html_file(out_file_name, body, nxt, prv, hme, division)

    def increase_bracket_level(self, action=None):
        self.bracket_level += 1
        if action:
            self.bracket_actions[self.bracket_level] = action
        
    def decrease_bracket_level(self):
        result = None
        if self.bracket_level in self.bracket_actions:
            action = self.bracket_actions[self.bracket_level]
            result = action()
            del self.bracket_actions[self.bracket_level]
        self.bracket_level -= 1
        return result

    def format_with_tag(self, tmpl, label, number="???", title="", **kws):
        full_label = self.chapter_name + "-" + label
        try:
            tag = stacks_project_info.label2tag(full_label)
        except:
            tag = "XXXX"
            print("WARNING: Tag not found: " + full_label)
        else:
            tag_cache[tag] = [number, self.chapter_name, self.division_number,
                              title]
        tagdiv = "<div class='tag'>"
        tagdiv += "<a href='http://stacks.math.columbia.edu/tag/{tag}'>"
        tagdiv += "{tag}</a></div>"
        tagdiv = tagdiv.format(tag=tag)
        return tmpl.format(tag=tag, number=number, title=title, tagdiv=tagdiv, **kws)

    @classmethod
    def process_chapter_list(cls):
        list_file_path = os.path.join(STACKS_DIR, "chapters.tex")
        chp_re = re.compile(r"\\item \\hyperref\[([-\w]*)\]")
        roman_numbers = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII",
                         "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI"]
        with open(list_file_path, "r") as list_file:
            part_number = 0
            part_tag = "0"
            for line in list_file.readlines():
                match = re.match(chp_re, line)
                if match:
                    label = match.group(1)
                    try:
                        tag = stacks_project_info.label2tag(label)
                    except:
                        print("WARNING: Tag not found: " + label)
                    else:
                        tag_cache.tag_children[part_tag].append(tag)
                elif line[0]!="\\":
                    part_number += 1
                    part_tag = str(part_number)
                    part_number2 = roman_numbers[part_number]
                    part_title = line[:-1]
                    tag_cache.tags[part_tag] = [part_number2, "", 0, part_title]
                    tag_cache.tag_children[""].append(part_tag)

    @classmethod
    def write_complete_toc(cls):
        toc_file_path = os.path.join(PROJECT_DIR, "web", "index.html")
        with open(toc_file_path, "w") as toc_file:
            with open(cls.header_file_name,"r") as header_file:
                shutil.copyfileobj(header_file, toc_file)
            body = "<div class='chapter' id='main-index'>\n"
            body += "<h1>Stacks Project</h1>\n"
            body += "<div class='toc'>\n"
            body += "<h2>Table of contents</h2>\n"
            body += "<ul>\n"
            for part in tag_cache.tag_children[""]:
                part_title = tag_cache[part][-1]
                body += "<li class='toc-part'>"
                body += part_title + "\n"
                for chp_tag in tag_cache.tag_children[part]:
                    chp_number, chp_name, _, chp_title = tag_cache[chp_tag]
                    chp_file = "{}-{:0>3}.html".format(chp_name, 0)
                    body += "<li>"
                    body += "<a class='toc-num' href='{}'>".format(chp_file)
                    body += "Chapter " + chp_number + "</a> "
                    body += "<a class='toc-title' href='{}'>".format(chp_file)
                    body += chp_title + "</a>"
                    body += "\n"
            body += "</ul>\n"
            body += "</div>\n"
            body += "</div>\n"
            print(body, file=toc_file)
            with open(cls.footer_file_name,"r") as footer_file:
                shutil.copyfileobj(footer_file, toc_file)

    @classmethod
    def process(cls, *chapters):
        print("initializing")
        if not chapters:
            write_toc = True
            chapters = stacks_project_info.chapters
        else:
            write_toc = False
            tag_cache.load()
        chapter_parsers = [ cls(chapter) for chapter in chapters ]
        for parser in chapter_parsers:
            print("parsing chapter: " + parser.chapter_name)
            parser.parse()
        for parser in chapter_parsers:
            print("writing chapter: " + parser.chapter_name)
            parser.write_files()
        if write_toc:
            print("writing index.html")
            cls.process_chapter_list()
            cls.write_complete_toc()
        print("finishing")
        tag_cache.save()

    @classmethod
    def rule(cls, regex):
        key = "a{}".format(len(cls.rules))
        regex = regex.replace("{", r"\{")
        regex = regex.replace("}", r"\}")
        cls.regex.append("(?P<{}>{})".format(key, regex))
        def decorator(transform_func):
            cls.rules[key] = transform_func
            return transform_func
        return decorator

    @classmethod
    def compile_regex(cls):
        cls.regex = re.compile("|".join(cls.regex))

#######################################################################
# Parser rules
#######################################################################

@Parser.rule(r"<")
def __(parser):
    return r"&lt;"

@Parser.rule(r">")
def __(parser):
    return r"&gt;"

@Parser.rule(r"\$\$")
def __(parser):
    if parser.math_mode:
        parser.math_mode = False
        return "\x06\n"
    else:
        parser.math_mode = True
        return "\n\x04dispay\x05"

@Parser.rule(r"\$")
def __(parser):
    if parser.math_mode:
        parser.math_mode = False
        return "\x06"
    else:
        parser.math_mode = True
        return "\x04normal\x05"
    # parser.math_mode = not parser.math_mode
    # return "$"

@Parser.rule(r"{\\it\s")
def __(parser):
    def action():
        return "</span>"
    parser.increase_bracket_level(action)
    return "<span class='it'>"

@Parser.rule(r"{\\bf\s")
def __(parser):
    def action():
        return "</span>"
    parser.increase_bracket_level(action)
    return "<span class='bf'>"

@Parser.rule(r"{\\bf\\large\s")
def __(parser):
    def action():
        return "</span>"
    parser.increase_bracket_level(action)
    return "<span class='bflarge'>"

@Parser.rule(r"(\\textbf{)")
def __(parser, s):
    if parser.math_mode:
        return s
    else:
        def action():
            return "</span>"
        parser.increase_bracket_level(action)
        return "<span class='bf'>"

@Parser.rule(r"(\\(textit|emph){)")
def __(parser, s, m):
    if parser.math_mode:
        return s
    else:
        def action():
            return "</span>"
        parser.increase_bracket_level(action)
        return "<span class='it'>"

@Parser.rule(r"{\\v (\w)}")
def __(parser, c):
    if not parser.math_mode:
        return "&{}caron;".format(c)
    else:
        return "{\\v " + c + "}"

@Parser.rule(r"{")
def __(parser):
    parser.bracket_level += 1
    return "{"

@Parser.rule(r"}")
def __(parser):
    result = parser.decrease_bracket_level()
    if result is not None:
        return result
    else:
        return "}"

# @Parser.rule(r"\\text{")
# def __(parser):
#     parser.math_mode = False
#     def action():
#         parser.math_mode = True
#     parser.increase_bracket_level(action)
#     return "\\text{"

@Parser.rule(r"\n *\n(?:\\medskip)?\\noindent")
def __(parser):
    parser.math_mode = False
    return "\n<p>\n"

@Parser.rule(r"\n\n")
def __(parser):
    if not parser.math_mode:
        return "\n<p>\n"

section_tmpl="""
<div class='section' id='{tag}'>{tagdiv}
<h2><span class='number'>&sect;{number}</span>{title}</h2>
"""

@Parser.rule(r"\\section{(.*)}\n\\label{(.*)}")
def __(parser, title, label):
    parser.math_mode = False
    if parser.section_number > 0:
        match_start = parser.current_match.start()
        if match_start - parser.division_start > 32*1024:
            parser.division_number += 1
            parser.division_first_section[parser.division_number] = parser.section_number
            parser.division_start = match_start
            out = "\n</div>\n\x02"
        else:
            out = "\n</div>\n"
    else:
        out = ""
    parser.section_number += 1
    parser.subsection_number = 0
    parser.equation_number = 0
    parser.division_last_section[parser.division_number] = parser.section_number
    number = "{}.{}".format(parser.chapter_number, parser.section_number)
    title = parser.parse(title)
    out += parser.format_with_tag(section_tmpl, label, number, title=title)
    return out

subsection_tmpl="""
<div class='subsection' id='{tag}'>{tagdiv}
<h3><span class='number'>&para;{number}</span>{title}</h3>
"""

@Parser.rule(r"\\subsection{(.*)}\n\\label{(.*)}")
def __(parser, title, label):
    parser.math_mode = False
    parser.subsection_number += 1
    parser.equation_number = 0
    number = "{}.{}.{}".format(
        parser.chapter_number, 
        parser.section_number,
        parser.subsection_number
    )
    title = parser.parse(title)
    return parser.format_with_tag(subsection_tmpl, label, number, title=title)

@Parser.rule(r"\\ref{([-\w]*)}")
def __(parser, label):
    label_type = label.split("-")[0]
    if label_type in stacks_project_info.label_types:
        label = parser.chapter_name + "-" + label
    try:
        tag = stacks_project_info.label2tag(label)
    except:
        print("WARNING: Tag not found: " + label)
        return "[" + label + "]"
    else:
        if parser.math_mode:
            return "\x01$" + tag
        else:
            return "\x01a" + tag

@Parser.rule(r"\\hyperref\[([-\w]*)\]{([^}]*)}")
def __(parser, label, text):
    text = parser.parse(text)
    label_type = label.split("-")[0]
    if label_type in stacks_project_info.label_types:
        label = parser.chapter_name + "-" + label
    try:
        tag = stacks_project_info.label2tag(label)
    except:
        print("WARNING: Tag not found: " + label)
        return "[" + label + "]"
    else:
        return "\x01a" + tag + "\x03" + text + "\x03"

cite_tmpl = "<a href='http://stacks.math.columbia.edu/bibliography/{cite}'>{cite}</a>"

@Parser.rule(r"\\cite\[([^\]]*)\]{([-\w]*)}")
def __(parser, comment, cite):
    # TODO: do this right
    comment = parser.parse(comment)
    cite = cite_tmpl.format(cite=cite)
    return "[" + cite + ", " + comment + "]"

@Parser.rule(r"\\cite{([-\w]*)}")
def __(parser, cite):
    # TODO: do this right
    cite = cite_tmpl.format(cite=cite)
    return "[" + cite + "]"

@Parser.rule(r"\\href{([^}]*)}{([^}]*)}")
def __(parser, link, text):
    return "<a href='{}'>{}</a>".format(link, text)

envs = "|".join([
	'lemma', 'proposition', 'theorem', 'remark', 'remarks',
	'example', 'exercise', 'situation', 'definition'
])

env_tmpl="""
<div class='thm {env}' id='{tag}'>{tagdiv}
<span class='thm-header'>{env}<span class='number'> {number}</span></span>
"""

@Parser.rule(r"\\begin{(" + envs + r")}\n\\label{(.*)}")
def __(parser, environ, label):
    parser.math_mode = False
    parser.subsection_number += 1
    parser.equation_number = 0
    number = "{}.{}.{}".format(
        parser.chapter_number, 
        parser.section_number,
        parser.subsection_number
    )
    return parser.format_with_tag(env_tmpl, label, number, env=environ)

env_tmpl2="""
<div class='thm {env}' id='{tag}'>{tagdiv}
<span class='thm-header'>{env}<span class='number'> {number}</span>
<span class='title'>{title}</span></span>
"""

@Parser.rule(r"\\begin{(" + envs + r")}\[([^\]]*)\]\n\\label{(.*)}")
def __(parser, environ, title, label):
    parser.math_mode = False
    parser.subsection_number += 1
    parser.equation_number = 0
    number = "{}.{}.{}".format(
        parser.chapter_number, 
        parser.section_number,
        parser.subsection_number
    )
    return parser.format_with_tag(env_tmpl2, label, number, title=title, env=environ)

@Parser.rule(r"\\end{(" + envs + ")}")
def __(parser, environ):
    parser.math_mode = False
    return "\n</div>\n"

@Parser.rule(r"\\begin{proof}")
def __(parser):
    parser.math_mode = False
    return "\n<div class='proof'>\n<span class='proof-header'>proof</span>\n"

@Parser.rule(r"\\end{proof}")
def __(parser):
    parser.math_mode = False
    return "\n</div>\n"

eqn_tmpl="""
<div class='equation' id='{tag}'>{tagdiv}
<span class='equation-label'>{number}</span>
\x04display\x05
"""

@Parser.rule(r"\\begin{equation}\n\\label{(.*)}")
def __(parser, label):
    parser.math_mode = True
    parser.equation_number += 1
    number = "{}.{}.{}.{}".format(
        parser.chapter_number, 
        parser.section_number,
        parser.subsection_number,
        parser.equation_number
    )
    return parser.format_with_tag(eqn_tmpl, label, number)

@Parser.rule(r"\\end{equation}")
def __(parser):
    parser.math_mode = False
    return "\n\x06\n</div>\n"

@Parser.rule(r"\\begin{enumerate}")
def __(parser):
    parser.math_mode = False
    parser.item_number = 1
    return "\n<ol>\n"

@Parser.rule(r"\\end{enumerate}")
def __(parser):
    parser.math_mode = False
    parser.item_number = 0
    return "\n</ol>\n"

@Parser.rule(r"\\begin{itemize}")
def __(parser):
    parser.math_mode = False
    parser.item_number = 1
    return "\n<ul>\n"

@Parser.rule(r"\\end{itemize}")
def __(parser):
    parser.math_mode = False
    parser.item_number = 0
    return "\n</ul>\n"

@Parser.rule(r"\\begin{center}")
def __(parser):
    parser.math_mode = False
    return "\n<div class='center'>\n"

@Parser.rule(r"\\end{center}")
def __(parser):
    parser.math_mode = False
    return "\n</div>\n"

@Parser.rule(r"\\begin{quote}")
def __(parser):
    parser.math_mode = False
    return "\n<div class='quote'>\n"

@Parser.rule(r"\\end{quote}")
def __(parser):
    parser.math_mode = False
    return "\n</div>\n"

@Parser.rule(r"\\begin{verbatim}")
def __(parser):
    parser.math_mode = False
    return "\n<pre>\n"

@Parser.rule(r"\\end{verbatim}")
def __(parser):
    parser.math_mode = False
    return "\n</pre>\n"

@Parser.rule(r"\\tableofcontents")
def __(parser):
    pass

@Parser.rule(r"(\\bigskip)")
def __(parser, s):
    if parser.math_mode:
        return s
    else:
        return "\n<p>\n"

@Parser.rule(r"(\\copyright)")
def __(parser, s):
    if parser.math_mode:
        return s
    else:
        return "&copy;"

@Parser.rule(r"\\item(.*)\n\\label{(.*)}")
def __(parser, tail, label):
    parser.math_mode = False
    number = parser.item_number
    parser.item_number += 1
    tmpl = "\n<li id='{tag}' class='item'>{tagdiv} {tail}\n"
    if tail:
        tail = parser.parse(tail)
    return parser.format_with_tag(tmpl, label, number, tail=tail)

@Parser.rule(r"\\item\[([^\]]*)\]")
def __(parser, c):
    parser.math_mode = False
    parser.item_number += 1
    out = "\n<li class='item manualcounter'>"
    out += "<span class='counter'>" + c + "</span>\n"
    return out

@Parser.rule(r"\\item")
def __(parser):
    parser.math_mode = False
    parser.item_number += 1
    return "\n<li class='item'>\n"

@Parser.rule(r"\\footnote{")
def __(parser):
    parser.math_mode = False
    parser.footnote_number += 1
    def action():
        return "</span></span>"
    parser.increase_bracket_level(action)
    out = "<a href='#footnote{n}' class='footnote-link'>{n}</a>"
    out += "<span class='footnote' id='footnote{n}'>"
    out += "<span class='footnote-content'>"
    out += "<span class='footnote-number'>{n}</span>"
    out = out.format(n=parser.footnote_number)
    return out

funny_envs = "slogan|reference|history"

@Parser.rule(r"\\begin{{({})}}".format(funny_envs))
def __(parser, env):
    parser.math_mode = False
    def action():
        return "</span></span>"
    parser.increase_bracket_level(action)
    out = "<span class='footnote'>"
    out += "<span class='footnote-content'>"
    out += "<span class='footnote-title'>{}</span>"
    out = out.format(env)
    return out

@Parser.rule(r"\\end{{({})}}".format(funny_envs))
def __(parser, env):
    parser.math_mode = False
    return parser.decrease_bracket_level()

@Parser.rule(r"~")
def __(parser):
    if parser.math_mode:
        return "~"
    else:
        return "&nbsp;"

@Parser.rule(r"``")
def __(parser):
    if parser.math_mode:
        return "``"
    else:
        return "&#8220;"

@Parser.rule(r"''")
def __(parser):
    if parser.math_mode:
        return "''"
    else:
        return "&#8221;"

@Parser.rule(r"---")
def __(parser):
    if parser.math_mode:
        return "---"
    else:
        return "&mdash;"

@Parser.rule(r"--")
def __(parser):
    if parser.math_mode:
        return "--"
    else:
        return "&ndash;"

@Parser.rule(r"\.\\ ")
def __(parser):
    if parser.math_mode:
        return ".\\ "
    else:
        return ".&nbsp;"

# \def\lim{\mathop{\rm lim}\nolimits}
# \def\colim{\mathop{\rm colim}\nolimits}
# \def\Hom{\mathop{\rm Hom}\nolimits}
# \def\Mor{\mathop{\rm Mor}\nolimits}
# \def\Ob{\mathop{\rm Ob}\nolimits}
# \def\Spec{\mathop{\rm Spec}}
# \def\SheafHom{\mathop{\mathcal{H}\!{\it om}}\nolimits}
# \def\Sh{\mathop{\textit{Sh}}\nolimits}
# \def\NL{\mathop{N\!L}\nolimits}
@Parser.rule(r"\\(lim|colim|Hom|Mor|Ob|Spec|SheafHom|Sh|NL)")
def __(parser, s):
    l = r"\nolimits"
    if s == "Spec":
        l = ""
    if s == "SheafHom":
        s = r"\mathcal{H}\!{\it om}"
    elif s == "Sh":
        s = r"\textit{Sh}"
    elif s == "NL":
        s = r"N\!L"
    else:
        s = r"\rm " + s
    return r"\mathop{{{}}}{}".format(s,l)

# \def\etale{{\acute{e}tale}}
@Parser.rule(r"\\etale")
def __(parser):
    if parser.math_mode:
        return "{&eacute;tale}"
    else:
        return "&eacute;tale"

# \def\proetale{{pro\text{-}\acute{e}tale}}
@Parser.rule(r"\\proetale")
def __(parser):
    if parser.math_mode:
        return "{pro-&eacute;tale}"
    else:
        return "pro-&eacute;tale"

# \def\Sch{\textit{Sch}}
# \def\QCoh{\textit{QCoh}}
@Parser.rule(r"\\(Sch|QCoh)")
def __(parser, op):
    return r"\textit{{{}}}".format(op)

# \def\Ker{\text{Ker}}
# \def\Im{\text{Im}}
# \def\Coker{\text{Coker}}
# \def\Coim{\text{Coim}}
@Parser.rule(r"\\(Ker|Im|Coker|Coim)")
def __(parser, op):
    return r"\text{{{}}}".format(op)

@Parser.rule(r"\\'(\w)")
def __(parser, c):
    return "&{}acute;".format(c)

@Parser.rule(r"\\'{(\w)}")
def __(parser, c):
    return "&{}acute;".format(c)

@Parser.rule(r"\\`(\w)")
def __(parser, c):
    return "&{}grave;".format(c)

@Parser.rule(r"\\`{(\w)}")
def __(parser, c):
    return "&{}grave;".format(c)

@Parser.rule(r'\\"(\w)')
def __(parser, c):
    return "&{}uml;".format(c)

@Parser.rule(r'\\"{(\w)}')
def __(parser, c):
    return "&{}uml;".format(c)

@Parser.rule(r"\\v{(\w)}")
def __(parser, c):
    if not parser.math_mode:
        return "&{}caron;".format(c)
    else:
        return "\\v{" + c + "}"

@Parser.rule(r"(\\%)")
def __(parser, s):
    if not parser.math_mode:
        return "%"
    else:
        return s

#######################################################################
# 
#######################################################################

Parser.compile_regex()

#######################################################################
# 
#######################################################################

if __name__ == "__main__":
    chapters = sys.argv[1:]
    Parser.process(*chapters)
