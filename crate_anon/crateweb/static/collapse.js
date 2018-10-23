/* collapse.js */

/* PLUS_IMAGE, MINUS_IMAGE are defined in the HTML, for static file URLs. */

var getElementsByClassName = function (className, tag, elm) {
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

/*  There are two ways of doing this:
    (1) Each thing has a collapse_detail and a collapse_summary div,
        which are alternated;
    (2) Different styles are applied to a single div.
    Option (2) is much more efficient when the thing being collapsed is
    lengthy, as option (1) duplicates it.
*/

function hasClass(div, className) {
    return div.classList.contains(className);
}

function removeClass(div, className) {
    div.classList.remove(className);
}

function addClass(div, className) {
    div.classList.add(className);
}

/* Must match CSS: */
var CLASS_COLLAPSIBLE = "collapsible",
    CLASS_PLUSMINUS_IMAGE = "plusminus_image",
    CLASS_VISIBLE = "collapse_visible",
    CLASS_INVISIBLE = "collapse_invisible",
    CLASS_BIG = "collapse_big",
    CLASS_SMALL = "collapse_small";

function setInvisible(div) {
    removeClass(div, CLASS_VISIBLE);
    removeClass(div, CLASS_BIG);
    removeClass(div, CLASS_SMALL);
    addClass(div, CLASS_INVISIBLE);
}

function setVisible(div) {
    removeClass(div, CLASS_INVISIBLE);
    removeClass(div, CLASS_BIG);
    removeClass(div, CLASS_SMALL);
    addClass(div, CLASS_VISIBLE);
}

function setBig(div) {
    removeClass(div, CLASS_INVISIBLE);
    removeClass(div, CLASS_VISIBLE);
    removeClass(div, CLASS_SMALL);
    addClass(div, CLASS_BIG);
}

function setSmall(div) {
    removeClass(div, CLASS_INVISIBLE);
    removeClass(div, CLASS_VISIBLE);
    removeClass(div, CLASS_BIG);
    addClass(div, CLASS_SMALL);
}

function showAll() {
    var elements = getElementsByClassName(CLASS_COLLAPSIBLE),
        i;
    for (i = 0; i < elements.length; ++i) {
        setVisible(elements[i]);
    }
    elements = getElementsByClassName(CLASS_PLUSMINUS_IMAGE);
    for (i = 0; i < elements.length; ++i) {
        // noinspection Annotator
        elements[i].src = MINUS_IMAGE;
    }
}

function hideAll() {
    var elements = getElementsByClassName(CLASS_COLLAPSIBLE),
        i;
    for (i = 0; i < elements.length; ++i) {
        setInvisible(elements[i]);
    }
    elements = getElementsByClassName(CLASS_PLUSMINUS_IMAGE);
    for (i = 0; i < elements.length; ++i) {
        // noinspection Annotator
        elements[i].src = PLUS_IMAGE;
    }
}

function expandAll() {
    var elements = getElementsByClassName(CLASS_COLLAPSIBLE),
        i;
    for (i = 0; i < elements.length; ++i) {
        setBig(elements[i]);
    }
    elements = getElementsByClassName(CLASS_PLUSMINUS_IMAGE);
    for (i = 0; i < elements.length; ++i) {
        // noinspection Annotator
        elements[i].src = PLUS_IMAGE;
    }
}

function collapseAll() {
    var elements = getElementsByClassName(CLASS_COLLAPSIBLE),
        i;
    for (i = 0; i < elements.length; ++i) {
        setSmall(elements[i]);
    }
    elements = getElementsByClassName(CLASS_PLUSMINUS_IMAGE);
    for (i = 0; i < elements.length; ++i) {
        // noinspection Annotator
        elements[i].src = MINUS_IMAGE;
    }
}

// noinspection JSUnusedGlobalSymbols
function toggleVisible(divId, imageId) {
    var div = document.getElementById(divId),
        img = document.getElementById(imageId);

    if (hasClass(div, CLASS_VISIBLE)) {
        setInvisible(div);
        // noinspection Annotator
        img.src = PLUS_IMAGE;
    } else {
        setVisible(div);
        // noinspection Annotator
        img.src = MINUS_IMAGE;
    }
}

// noinspection JSUnusedGlobalSymbols
function toggleCollapsed(divId, imageId) {
    var div = document.getElementById(divId),
        img = document.getElementById(imageId);

    if (hasClass(div, CLASS_BIG)) {
        setSmall(div);
        // noinspection Annotator
        img.src = PLUS_IMAGE;
    } else {
        setBig(div);
        // noinspection Annotator
        img.src = MINUS_IMAGE;
    }
}
