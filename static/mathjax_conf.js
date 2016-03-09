window.MathJax = { AuthorInit: function() {

    MathJax.Ajax.config.path["Contrib"] = "http://cdn.mathjax.org/mathjax/contrib";

    MathJax.Hub.Config({
        extensions: ["tex2jax.js"],
        jax: ["input/TeX", "output/HTML-CSS"],
        tex2jax: {
            inlineMath: [ ['$','$'], ["\\(","\\)"] ],
            processRefs: false,
            processEscapes: true
        },
        'HTML-CSS': { 
            scale: 95,
            availableFonts: ["TeX"]
        },
        TeX: {
            extensions: [ "[Contrib]/xyjax/xypic.js",
                          "AMSmath.js",
                          "AMSsymbols.js",
                          "noErrors.js",
                          "noUndefined.js"
                        ]
        }
    });

}};

window.onload = function() {
    var next_url = document.getElementById("nav-next").href;
    window.onkeyup = function(ev) {
      var key = event.keyCode || event.which;
      if (key == 39) {
          window.history.forward();
          window.location.href = next_url;
      }
      else if (key == 37) {
          window.history.back();
      }
    }
}
