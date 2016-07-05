/*
-   The Document Object Model (DOM) is built in. So is Javascript.
    Libraries like jQuery aren't.
    Using Javascript to talk to the DOM:
        http://www.w3schools.com/js/js_htmldom_methods.asp
-   The querySelector method is newer than getElementById (but ?less supported).
-   Editing a select list:
    http://stackoverflow.com/questions/6364748/change-the-options-array-of-a-select-list

*/
var COLTYPE_STRING = "string",
    COLTYPE_STRING_FULLTEXT = "string_fulltext",
    COLTYPE_INTEGER = "integer",
    COLTYPE_DATE = "date",
    // All ID_* values must match HTML id tags.
    // ID_ANNOUNCEMENT = "id_announcement",
    ID_COLTYPE = "id_coltype",
    ID_COLUMN_PICKER = "id_column",
    ID_COMMENT = "id_comment",
    ID_TABLE_PICKER = "id_table",
    ID_WHERE_OP = "id_where_op",
    ID_WHERE_VALUE_DATE = "id_where_value_date",
    ID_WHERE_VALUE_FILE = "id_file",
    ID_WHERE_VALUE_TEXT = "id_where_value_text",
    ID_WHERE_VALUE_NUMBER = "id_where_value_number",
    OPS_INTEGER_DATE = [
        {value: "<", text: "<"},
        {value: "<=", text: "<="},
        {value: "=", text: "="},
        {value: "!=", text: "!= (not equal)"},
        {value: ">=", text: ">="},
        {value: ">", text: ">"},
        {value: "IN", text: "IN"},
        {value: "NOT IN", text: "NOT IN"},
    ],
    OPS_STRING = [
        {value: "=", text: "="},
        {value: "!=", text: "!= (not equal)"},
        {value: "LIKE", text: "LIKE (use % as wildcard)"},
        {value: "IN", text: "IN"},
        {value: "NOT IN", text: "NOT IN"},
    ],
    OPS_STRING_FULLTEXT = OPS_STRING.concat([
        {value: "MATCH", text: "MATCH (use whole words)"},
    ]),
    OPS_USING_FILE = ["IN", "NOT IN"],
    // The variables that follow are pre-populated by the server.
    tables_fields = [
        {
            table: 'table1',
            columns: [
                {colname: 't1_col1_str', coltype: COLTYPE_STRING, comment: "comment 1"},
                {colname: 't1_col2_str_ft', coltype: COLTYPE_STRING_FULLTEXT, comment: "comment 2"},
                {colname: 't1_col3_int', coltype: COLTYPE_INTEGER, comment: "comment 3"},
                {colname: 't1_col4_date', coltype: COLTYPE_DATE, comment: "comment 4"},
            ],
        },
        {
            table: 'table2',
            columns: [
                {colname: 't2_col1', coltype: COLTYPE_STRING, comment: ""},
                {colname: 't2_col2', coltype: COLTYPE_STRING, comment: ""},
                {colname: 't2_col3', coltype: COLTYPE_STRING, comment: ""},
            ],
        },
    ],
    starting_table = "table2",
    starting_column = "t2_col3";

// ============================================================================
// Read table/column information from variables passed in
// ============================================================================

function get_all_table_names() {
    var table_names = [],
        i;
    for (i = 0; i < tables_fields.length; ++i) {
        table_names.push(tables_fields[i].table);
    }
    return table_names;
}

function get_table_info(table) {
    var i;
    for (i = 0; i < tables_fields.length; ++i) {
        if (tables_fields[i].table == table) {
            return tables_fields[i];
        }
    }
}

function get_all_column_names(table) {
    var tableinfo = get_table_info(table),
        column_names = [],
        i;
    // log("get_all_column_names: " + table);
    for (i = 0; i < tableinfo.columns.length; ++i) {
        column_names.push(tableinfo.columns[i].colname);
    }
    return column_names;
}

function get_column_info(table, column) {
    var tableinfo = get_table_info(table),
        i;
    for (i = 0; i < tableinfo.columns.length; ++i) {
        if (tableinfo.columns[i].colname == column) {
            return tableinfo.columns[i];
        }
    }
}

// ============================================================================
// HTML manipulation
// ============================================================================

function reset_select_options(element, options) {
    // options should be a list of objects with attributes: text, value
    var i,
        opt;
    while (element.options.length > 0) {
        element.remove(element.options.length - 1);
    }
    for (i = 0; i < options.length; ++i) {
        opt = document.createElement('option');
        opt.text = options[i].text;
        opt.value = options[i].value;
        element.add(opt, null);
    }
}

// ============================================================================
// Ancillary functions
// ============================================================================

/*
function demo_change() {
    document.getElementById(ID_WHERE_VALUE_TEXT).value = "Something changed!";
    announce("Announcement!");
}
*/

/*
function announce(text) {
    document.getElementById(ID_ANNOUNCEMENT).innerHTML = text;
}
*/

function log(text) {
    console.log(text);
}

function hide(element) {
    // Used for input elements
    element.style.display = 'none';  // for any element
    element.disabled = true;  // for input elements
}

function show(element, method) {
    // Used for input elements
    method = method || 'inline';  // specify 'inline' or 'block'
    element.style.display = method;
    element.disabled = false;  // for input elements
}

function set_picker_by_value(element, value) {
    var i;
    for (i = 0; i < element.options.length; ++i) {
        if (element.options[i].value == value) {
            element.selectedIndex = i;
            break;
        }
    }
}

// ============================================================================
// Readers
// ============================================================================

function get_current_table() {
    var table_picker = document.getElementById(ID_TABLE_PICKER);
    return table_picker.options[table_picker.selectedIndex].value;
}

function get_current_column() {
    var column_picker = document.getElementById(ID_COLUMN_PICKER);
    return column_picker.options[column_picker.selectedIndex].value;
}

function get_current_coltype() {
    var coltype_hidden_input = document.getElementById(ID_COLTYPE);
    return coltype_hidden_input.value;
}

function get_current_op() {
    var where_op_picker = document.getElementById(ID_WHERE_OP);
    return where_op_picker.options[where_op_picker.selectedIndex].value;
}

// ============================================================================
// Logic
// ============================================================================

function set_table(table) {
    var table_picker = document.getElementById(ID_TABLE_PICKER);
    set_picker_by_value(table_picker, table);
}

function set_column(column) {
    var column_picker = document.getElementById(ID_COLUMN_PICKER);
    set_picker_by_value(column_picker, column);
}

function where_op_changed() {
    var entry_text = document.getElementById(ID_WHERE_VALUE_TEXT),
        entry_number = document.getElementById(ID_WHERE_VALUE_NUMBER),
        entry_date = document.getElementById(ID_WHERE_VALUE_DATE),
        entry_file = document.getElementById(ID_WHERE_VALUE_FILE),
        coltype = get_current_coltype(),
        op = get_current_op();
    hide(entry_text);
    hide(entry_number);
    hide(entry_date);
    hide(entry_file);
    if (OPS_USING_FILE.indexOf(op) !== -1) {
        show(entry_file);
    } else {
        switch (coltype) {
            case COLTYPE_STRING:
            case COLTYPE_STRING_FULLTEXT:
                show(entry_text);
                break;
            case COLTYPE_INTEGER:
                show(entry_number);
                break;
            case COLTYPE_DATE:
                show(entry_date);
                break;
            default:
                // log("error: unknown column type " + coltype);
                break;
        }
    }
}

function column_changed() {
    var coltype_hidden_input = document.getElementById(ID_COLTYPE),
        where_op_picker = document.getElementById(ID_WHERE_OP),
        current_column_info = document.getElementById("id_current_column"),
        table = get_current_table(),
        column = get_current_column(),
        colinfo = get_column_info(table, column),
        coltype = colinfo.coltype,
        comment = colinfo.comment;
    // log("column_changed: coltype: " + coltype);
    coltype_hidden_input.value = coltype;
    switch (coltype) {
        case COLTYPE_STRING:
            reset_select_options(where_op_picker, OPS_STRING);
            break;
        case COLTYPE_STRING_FULLTEXT:
            reset_select_options(where_op_picker, OPS_STRING_FULLTEXT);
            break;
        case COLTYPE_INTEGER:
            reset_select_options(where_op_picker, OPS_INTEGER_DATE);
            break;
        case COLTYPE_DATE:
            reset_select_options(where_op_picker, OPS_INTEGER_DATE);
            break;
        default:
            // log("error: unknown column type " + coltype);
            break;
    }
    current_column_info.innerHTML = table + "." + column;
    document.getElementById(ID_COMMENT).innerHTML = comment || "&nbsp;";
    where_op_changed();
}

function table_changed() {
    var column_picker = document.getElementById(ID_COLUMN_PICKER),
        table = get_current_table(),
        column_names = get_all_column_names(table),
        i,
        cname,
        column_options = [];
    // log("table_changed");
    for (i = 0; i < column_names.length; ++i) {
        cname = column_names[i];
        column_options.push({text: cname, value: cname})
    }
    reset_select_options(column_picker, column_options);
    column_changed();
}

function populate() {
    var table_picker = document.getElementById(ID_TABLE_PICKER),
        column_picker = document.getElementById(ID_COLUMN_PICKER),
        where_op_picker = document.getElementById(ID_WHERE_OP),
        i,
        tname,
        table_names = get_all_table_names(),
        table_options = [];
    // log("populate");
    // log("... table_names: " + table_names);
    for (i = 0; i < table_names.length; ++i) {
        tname = table_names[i];
        table_options.push({text: tname, value: tname});
    }
    // log("... table_options: " + table_options);
    where_op_picker.addEventListener("change", where_op_changed);
    column_picker.addEventListener("change", column_changed);
    reset_select_options(table_picker, table_options);
    if (starting_table) {
        set_table(starting_table);
    }
    table_changed();
    table_picker.addEventListener("change", table_changed);
    if (starting_column) {
        set_column(starting_column);
    }
    // announce("Loaded!");
}
