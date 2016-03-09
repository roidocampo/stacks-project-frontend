#!/usr/bin/env node

const readline = require('readline');
const katex = require('katex');

const rl = readline.createInterface({
    input: process.stdin, 
    output: process.stdout,
    terminal: false
});

var html;

rl.on('line', (line) => {

    try {
        html = "1" + katex.renderToString(line);
    } catch(err) {
        html = "0" + line;
    }
    html = html.replace(/\r?\n/g, " ");
    console.log(html);

}).on('close', () => {

    process.exit(0);

});

