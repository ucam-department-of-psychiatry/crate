/* collapse.js */
/* {% load staticfiles %} {# so that static routing works with non-root Django #} */

var PLUS_IMAGE = '{% static "plus.gif" %}',
    MINUS_IMAGE = '{% static "minus.gif" %}';

var getElementsByClassName = function (className, tag, elm){
    // http://robertnyman.com/2008/05/27/
    //        the-ultimate-getelementsbyclassname-anno-2008/
    // Developed by Robert Nyman, http://www.robertnyman.com
    // Code/licensing: http://code.google.com/p/getelementsbyclassname/
    if (document.getElementsByClassName) {
        getElementsByClassName = function (className, tag, elm) {
            elm = elm || document;
            var elements = elm.getElementsByClassName(className),
                nodeName = (
                    tag
                    ? new RegExp("\\b" + tag + "\\b", "i")
                    : null
                ),
                returnElements = [],
                current;
            for(var i=0, il=elements.length; i<il; i+=1){
                current = elements[i];
                if (!nodeName || nodeName.test(current.nodeName)) {
                    returnElements.push(current);
                }
            }
            return returnElements;
        };
    } else if (document.evaluate) {
        getElementsByClassName = function (className, tag, elm) {
            tag = tag || "*";
            elm = elm || document;
            var classes = className.split(" "),
                classesToCheck = "",
                xhtmlNamespace = "http://www.w3.org/1999/xhtml",
                namespaceResolver = (
                    document.documentElement.namespaceURI
                        === xhtmlNamespace
                    ? xhtmlNamespace
                    : null
                ),
                returnElements = [],
                elements,
                node;
            for (var j=0, jl=classes.length; j<jl; j+=1){
                classesToCheck += (
                    "[contains(concat(' ', @class, ' '), ' "
                    + classes[j]
                    + " ')]"
                );
            }
            try {
                elements = document.evaluate(
                    ".//" + tag + classesToCheck, elm,
                    namespaceResolver, 0, null
                );
            }
            catch (e) {
                elements = document.evaluate(
                    ".//" + tag + classesToCheck, elm, null, 0, null
                );
            }
            while ((node = elements.iterateNext())) {
                returnElements.push(node);
            }
            return returnElements;
        };
    } else {
        getElementsByClassName = function (className, tag, elm) {
            tag = tag || "*";
            elm = elm || document;
            var classes = className.split(" "),
                classesToCheck = [],
                elements = (
                    (tag === "*" && elm.all)
                    ? elm.all
                    : elm.getElementsByTagName(tag)
                ),
                current,
                returnElements = [],
                match;
            for (var k=0, kl=classes.length; k<kl; k+=1) {
                classesToCheck.push(new RegExp("(^|\\s)" + classes[k]
                                    + "(\\s|$)"));
            }
            for (var l=0, ll=elements.length; l<ll; l+=1) {
                current = elements[l];
                match = false;
                for (var m=0, ml=classesToCheck.length; m<ml; m+=1) {
                    match = classesToCheck[m].test(current.className);
                    if (!match) {
                        break;
                    }
                }
                if (match) {
                    returnElements.push(current);
                }
            }
            return returnElements;
        };
    }
    return getElementsByClassName(className, tag, elm);
};

function hideAll() {
    var elements = getElementsByClassName("collapse_detail"),
        i;
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "none";
    }
    elements = getElementsByClassName("collapse_summary");
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "";
    }
    elements = getElementsByClassName("plusminus_image");
    for (i = 0; i < elements.length; ++i) {
        elements[i].src = PLUS_IMAGE;
    }
}

function showAll() {
    var elements = getElementsByClassName("collapse_detail"),
        i;
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "";
    }
    elements = getElementsByClassName("collapse_summary");
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "none";
    }
    elements = getElementsByClassName("plusminus_image");
    for (i = 0; i < elements.length; ++i) {
        elements[i].src = MINUS_IMAGE;
    }
}

function toggle(divId, imageId, summaryDivId) {
    var div = document.getElementById(divId),
        img = document.getElementById(imageId),
        alt = (summaryDivId === undefined
                ? null
                : document.getElementById(summaryDivId));

    if (div.style.display == "none") {
        div.style.display = "";
        img.src = MINUS_IMAGE;
        if (alt) {
            alt.style.display = "none";
        }
    } else {
        div.style.display = "none";
        img.src = PLUS_IMAGE;
        if (alt) {
            alt.style.display = "";
        }
    }
}
