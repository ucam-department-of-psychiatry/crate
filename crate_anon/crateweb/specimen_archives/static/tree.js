/*

crate_anon/crateweb/specimen_archives/static/tree.js

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

Dynamic selection trees for the CRATE archive views.

See https://www.w3schools.com/howto/howto_js_treeview.asp

*/

function activateTreeExpansion()
{
    // Makes all trees in the document active.
    // - Nodes that can be expanded/collapsed should have the class "caret".
    // - They should be siblings of an element (e.g. <ul>) called "nested",
    //   containing the content.

    var toggler = document.getElementsByClassName("caret");
    for (var i = 0; i < toggler.length; i++) {
      toggler[i].addEventListener("click", function() {
        this.parentElement.querySelector(".nested").classList.toggle("active");
        this.classList.toggle("caret-down");
      });
    }
}


function createCallback(fn, param)
{
    // https://stackoverflow.com/questions/750486/javascript-closure-inside-loops-simple-practical-example
    return function() {
        fn(param);
    }
}


function treeNodeHasChildren(node)
{
    var ul_elements = node.getElementsByTagName("ul");
    return ul_elements.length > 0;
}


function addTreeIDCallbacks(tree_id, handler_fn)
{
    // Adds callbacks to all items in a tree.
    // When clicked, they will call handler_fn(css_id_of_item).

    var tree = document.getElementById(tree_id);
    if (tree === null) {
        console.log("Error: no element with ID '" + tree_id + "'");
        return;
    }
    // Find all "<li>" elements within it, EXCEPT those with class "caret":
    var li_elements = tree.getElementsByTagName("li");
    for (var i = 0; i < li_elements.length; i++) {
        var node = li_elements[i];
        if (treeNodeHasChildren(node)) {
            continue;
        }
        // Set callback.
        node.onclick = createCallback(handler_fn, node.id);
    }
}


function setElementClassName(element_id, classname)
{
    var element = document.getElementById(element_id);
    if (element === null) {
        console.log("Error: no element with ID '" + element_id + "'");
        return;
    }
    element.className = classname;
}
