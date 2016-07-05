/*
-   The Document Object Model (DOM) is built in. So is Javascript.
    Libraries like jQuery aren't.
    Using Javascript to talk to the DOM:
        http://www.w3schools.com/js/js_htmldom_methods.asp
-   The querySelector method is newer than getElementById (but ?less supported).
-   Editing a select list:
    http://stackoverflow.com/questions/6364748/change-the-options-array-of-a-select-list

-   Practicalities:

    Using an "AND NOT" button becomes confusing the first time you enter a
    condition. Offer negated conditions, but only AND as a where-condition
    joiner.

    Using OR becomes tricky in terms of precedence; use SQL.

    Using IN becomes tricky using standard input fields (e.g. an int-validation
    field won't allow int CSV input). But we can use files instead.

    Not equals: <> in ANSI SQL, but != is supported by MySQL and clearer.

*/
    // DATATYPE_* values must match research.forms.QueryBuilderForm
var DATATYPE_DATE = "date",
    DATATYPE_FLOAT = "float",
    DATATYPE_INTEGER = "int",
    DATATYPE_STRING = "string",
    DATATYPE_STRING_FULLTEXT = "string_fulltext",
    DATATYPE_UNKNOWN = "unknown",
    // All ID_* values must match HTML id tags.
    // ID_ANNOUNCEMENT = "id_announcement",
    ID_COLTYPE = "id_coltype",
    ID_COLTYPE_INFO = "id_coltype_info",
    ID_COLUMN_PICKER = "id_column",
    ID_COMMENT = "id_comment",
    ID_CURRENT_COLUMN = "id_current_column",
    ID_SCHEMA_PICKER = "id_schema",
    ID_TABLE_PICKER = "id_table",
    ID_OFFER_WHERE = "id_offer_where",
    ID_WARNING = "id_warning",
    ID_WHERE_OP = "id_where_op",
    ID_WHERE_BUTTON = "id_where_button",
    ID_WHERE_VALUE_DATE = "id_where_value_date",
    ID_WHERE_VALUE_FILE = "id_file",
    ID_WHERE_VALUE_FLOAT = "id_where_value_float",
    ID_WHERE_VALUE_INTEGER = "id_where_value_integer",
    ID_WHERE_VALUE_TEXT = "id_where_value_text",
    OPS_NONE = [],
    OPS_IN_NULL = [
        {value: "IN", text: "IN"},
        {value: "NOT IN", text: "NOT IN"},
        {value: "IS NULL", text: "IS NULL"},
        {value: "IS NOT NULL", text: "IS NOT NULL"}
    ],
    OPS_NUMBER_DATE = [
        {value: "<", text: "<"},
        {value: "<=", text: "<="},
        {value: "=", text: "="},
        {value: "!=", text: "!= (not equals)"},
        {value: ">=", text: ">="},
        {value: ">", text: ">"}
    ].concat(OPS_IN_NULL),
    OPS_STRING_BASE = [
        {value: "=", text: "="},
        {value: "!=", text: "!= (not equal)"},
        {value: "LIKE", text: "LIKE (use % as wildcard)"},
        {value: "REGEXP", text: "REGEXP (regular expression match)"}
    ],
    OPS_STRING = OPS_STRING_BASE.concat(OPS_IN_NULL),
    OPS_STRING_FULLTEXT = OPS_STRING_BASE.concat([
        {value: "MATCH", text: "MATCH (match whole words)"}
    ]).concat(OPS_IN_NULL),
    OPS_USING_FILE = ["IN", "NOT IN"],
    OPS_USING_NULL = ["IS NULL", "IS NOT NULL"];

// The variables that follow are pre-populated by the server.
/* Examples:
var DATABASE_STRUCTURE = [
        {
            schema: 'schema1',
            tables: [
                {
                    table: 'table1',
                    columns: [
                        {colname: 't1_col1_str', coltype: DATATYPE_STRING, comment: "comment 1"},
                        {colname: 't1_col2_str_ft', coltype: DATATYPE_STRING_FULLTEXT, comment: "comment 2"},
                        {colname: 't1_col3_int', coltype: DATATYPE_INTEGER, comment: "comment 3"},
                        {colname: 't1_col4_date', coltype: DATATYPE_DATE, comment: "comment 4"}
                    ],
                },
                {
                    table: 'table2',
                    columns: [
                        {colname: 't2_col1', coltype: DATATYPE_STRING, comment: ""},
                        {colname: 't2_col2', coltype: DATATYPE_STRING, comment: ""},
                        {colname: 't2_col3', coltype: DATATYPE_STRING, comment: ""}
                    ]
                }
            ]
        }
    ],
    STARTING_VALUES = {
        schema: "schema1",
        table: "table2",
        column: "t2_col3",
        // ... etc.; see research/views.py
    };
*/

// ============================================================================
// Read table/column information from variables passed in
// ============================================================================

function get_all_schema_names() {
    var schema_names = [],
        i;
    for (i = 0; i < DATABASE_STRUCTURE.length; ++i) {
        schema_names.push(DATABASE_STRUCTURE[i].schema);
    }
    return schema_names;
}

function get_schema_info(schema) {
    var i;
    for (i = 0; i < DATABASE_STRUCTURE.length; ++i) {
        if (DATABASE_STRUCTURE[i].schema == schema) {
            return DATABASE_STRUCTURE[i];
        }
    }
    return null;
}

function get_all_table_names(schema) {
    var schema_info = get_schema_info(schema),
        table_names = [],
        i;
    if (schema_info === null) {
        return [];
    }
    for (i = 0; i < schema_info.tables.length; ++i) {
        table_names.push(schema_info.tables[i].table);
    }
    return table_names;
}

function get_table_info(schema, table) {
    var schema_info = get_schema_info(schema),
        i;
    if (schema_info === null) {
        return null;
    }
    for (i = 0; i < schema_info.tables.length; ++i) {
        if (schema_info.tables[i].table == table) {
            return schema_info.tables[i];
        }
    }
    return null;
}

function get_all_column_names(schema, table) {
    var tableinfo = get_table_info(schema, table),
        column_names = [],
        i;
    if (tableinfo === null) {
        return [];
    }
    for (i = 0; i < tableinfo.columns.length; ++i) {
        column_names.push(tableinfo.columns[i].colname);
    }
    return column_names;
}

function get_column_info(schema, table, column) {
    var tableinfo = get_table_info(schema, table),
        i;
    if (tableinfo === null) {
        return null;
    }
    for (i = 0; i < tableinfo.columns.length; ++i) {
        if (tableinfo.columns[i].colname == column) {
            return tableinfo.columns[i];
        }
    }
}

// ============================================================================
// Ancillary and HTML/DOM manipulation functions
// ============================================================================

function log(text) {
    console.log(text);
}

function get_select_options_from_list(valuelist) {
    var i,
        val,
        options = [];
    for (i = 0; i < valuelist.length; ++i) {
        val = valuelist[i];
        options.push({text: val, value: val});
    }
    return options;
}

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

function reset_select_options_by_id(element_id, options) {
    var element = document.getElementById(element_id);
    reset_select_options(element, options);
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function hide_element(element) {
    // For any element.
    element.style.display = 'none';  // for any element
}

function show_element(element, method) {
    // For any element.
    method = method || 'inline';  // specify 'inline' or 'block'
    element.style.display = method;
}

function hide_input(element) {
    // For <input> elements.
    // The "disabled" option means that the input's data will not be submitted.
    hide_element(element);
    element.disabled = true;
}

function show_input(element, method) {
    // For <input> elements.
    show_element(element, method);
    element.disabled = false;
}

function set_picker_value_by_id(element_id, value, default_value) {
    // For <select ...> <option ...> <option ...> </select> elements.
    var element = document.getElementById(element_id),
        i;
    if (value) {
        for (i = 0; i < element.options.length; ++i) {
            if (element.options[i].value == value) {
                element.selectedIndex = i;
                return;
            }
        }
    } else if (default_value) {
        for (i = 0; i < element.options.length; ++i) {
            if (element.options[i].value == default_value) {
                element.selectedIndex = i;
                return;
            }
        }
    }
}

function get_picker_value_by_id(element_id) {
    var element = document.getElementById(element_id);
    if (element.selectedIndex < 0) {
        return "";
    }
    return element.options[element.selectedIndex].value;
}

function set_input_value_by_id(id, value) {
    // For <input ... value=""> elements
    var element = document.getElementById(id);
    element.value = value;
}

function get_input_value_by_id(id) {
    // For <input ... value=""> elements
    var element = document.getElementById(id);
    return element.value;
}

function set_checkbox_input_by_id(id, value) {
    // For <input ... type="checkbox" ...>
    var element = document.getElementById(id);
    // http://stackoverflow.com/questions/7851868/whats-the-proper-value-for-a-checked-attribute-of-an-html-checkbox
    // http://stackoverflow.com/questions/208105/how-do-i-remove-a-property-from-a-javascript-object
    if (value) {
        element.checked = "checked";
    } else {
        delete element.checked;
    }
}

function set_hidden_boolean_input_by_id(id, value) {
    set_input_value_by_id(id, value ? "True" : "False");
}

function display_html_by_id(element_id, text, append, sep) {
    append = append === null ? false : append;
    sep = sep === null ? "<br>" : sep;
    var element = document.getElementById(element_id);
    if (append) {
        if (element.innerHTML) {
            element.innerHTML += sep;
        }
        element.innerHTML += text;
    } else {
        element.innerHTML = text;
    }
}

function warn(text) {
    display_html_by_id(ID_WARNING, text, true);
}

/*
function demo_change() {
    set_input_value_by_id(ID_WHERE_VALUE_TEXT, "Something changed!");
    announce("Announcement!");
}
*/

/*
function announce(text) {
    display_html_by_id(ID_ANNOUNCEMENT, text);
}
*/

// ============================================================================
// Readers
// ============================================================================

function get_current_schema() {
    return get_picker_value_by_id(ID_SCHEMA_PICKER);
}

function get_current_table() {
    return get_picker_value_by_id(ID_TABLE_PICKER);
}

function get_current_column() {
    return get_picker_value_by_id(ID_COLUMN_PICKER);
}

function get_current_coltype() {
    return get_input_value_by_id(ID_COLTYPE);
}

function get_current_op() {
    return get_picker_value_by_id(ID_WHERE_OP);
}

// ============================================================================
// Logic
// ============================================================================

function set_schema(schema) {
    set_picker_value_by_id(ID_SCHEMA_PICKER, schema);
    schema_changed();
}

function set_table(table) {
    set_picker_value_by_id(ID_TABLE_PICKER, table);
    table_changed();
}

function set_column(column) {
    set_picker_value_by_id(ID_COLUMN_PICKER, column);
    column_changed();
}

function set_op(op, default_op) {
    set_picker_value_by_id(ID_WHERE_OP, op, default_op || "=");
    where_op_changed();
}

function where_op_changed() {
    var entry_date = document.getElementById(ID_WHERE_VALUE_DATE),
        entry_file = document.getElementById(ID_WHERE_VALUE_FILE),
        entry_float = document.getElementById(ID_WHERE_VALUE_FLOAT),
        entry_integer = document.getElementById(ID_WHERE_VALUE_INTEGER),
        entry_text = document.getElementById(ID_WHERE_VALUE_TEXT),
        coltype = get_current_coltype(),
        op = get_current_op();
    // log("where_op_changed");
    hide_input(entry_date);
    hide_input(entry_file);
    hide_input(entry_float);
    hide_input(entry_integer);
    hide_input(entry_text);
    if (!STARTING_VALUES.offer_where) {
        return;
    }
    if (OPS_USING_FILE.indexOf(op) !== -1) {
        show_input(entry_file);
    } else if (OPS_USING_NULL.indexOf(op) !== -1) {
        // show nothing
    } else {
        switch (coltype) {
            case DATATYPE_DATE:
                show_input(entry_date);
                break;
            case DATATYPE_FLOAT:
                show_input(entry_float);
                break;
            case DATATYPE_INTEGER:
                show_input(entry_integer);
                break;
            case DATATYPE_STRING:
            case DATATYPE_STRING_FULLTEXT:
                show_input(entry_text);
                break;
            case DATATYPE_UNKNOWN:
                break;
            default:
                break;
        }
    }
}

function column_changed() {
    var where_op_picker = document.getElementById(ID_WHERE_OP),
        where_button = document.getElementById(ID_WHERE_BUTTON),
        schema = get_current_schema(),
        table = get_current_table(),
        column = get_current_column(),
        colinfo = get_column_info(schema, table, column),
        old_op = get_current_op(),
        coltype = colinfo.coltype,
        rawtype = colinfo.rawtype,
        comment = colinfo.comment,
        colinfo_html = "";
    // log("column_changed: coltype: " + coltype);
    set_input_value_by_id(ID_COLTYPE, coltype);
    if (schema == STARTING_VALUES.default_schema) {
        colinfo_html = "<i>[default schema]</i>&nbsp;";
    } else {
        colinfo_html = "<i>" + schema + "</i>.";
    }
    colinfo_html += table + ".<b>" + column + "</b>";
    display_html_by_id(ID_CURRENT_COLUMN, colinfo_html);
    display_html_by_id(
        ID_COMMENT,
        ("<i>" + escapeHtml(comment) + "</i>") || "&nbsp;");
    display_html_by_id(
        ID_COLTYPE_INFO,
        "Type: " + coltype + " (SQL type: " + rawtype + ")");
    if (!STARTING_VALUES.offer_where || coltype == DATATYPE_UNKNOWN) {
        reset_select_options(where_op_picker, OPS_NONE);
        hide_element(where_op_picker);
        hide_element(where_button);
    } else {
        switch (coltype) {
            case DATATYPE_DATE:
            case DATATYPE_FLOAT:
            case DATATYPE_INTEGER:
                reset_select_options(where_op_picker, OPS_NUMBER_DATE);
                break;
            case DATATYPE_STRING:
                reset_select_options(where_op_picker, OPS_STRING);
                break;
            case DATATYPE_STRING_FULLTEXT:
                reset_select_options(where_op_picker, OPS_STRING_FULLTEXT);
                break;
            default:
                reset_select_options(where_op_picker, OPS_NONE);
                warn("Error: unknown column type " + coltype);
                break;
        }
    }
    set_op(old_op);
}

function table_changed() {
    var schema = get_current_schema(),
        table = get_current_table(),
        column_names = get_all_column_names(schema, table),
        column_options = get_select_options_from_list(column_names);
    // log("table_changed");
    reset_select_options_by_id(ID_COLUMN_PICKER, column_options);
    column_changed();
}

function schema_changed() {
    var schema = get_current_schema(),
        table_names = get_all_table_names(schema),
        table_options = get_select_options_from_list(table_names);
    // log("schema_changed");
    reset_select_options_by_id(ID_TABLE_PICKER, table_options);
    table_changed();
}

function populate() {
    var schema_picker = document.getElementById(ID_SCHEMA_PICKER),
        table_picker = document.getElementById(ID_TABLE_PICKER),
        column_picker = document.getElementById(ID_COLUMN_PICKER),
        where_op_picker = document.getElementById(ID_WHERE_OP),
        schema_names = get_all_schema_names(),
        schema_options = get_select_options_from_list(schema_names);
    // log("populate");
    schema_picker.addEventListener("change", schema_changed);
    table_picker.addEventListener("change", table_changed);
    column_picker.addEventListener("change", column_changed);
    where_op_picker.addEventListener("change", where_op_changed);
    reset_select_options(schema_picker, schema_options);
    set_schema(STARTING_VALUES.schema);
    set_table(STARTING_VALUES.table);
    set_column(STARTING_VALUES.column);
    set_op(STARTING_VALUES.op);
    set_input_value_by_id(ID_WHERE_VALUE_DATE, STARTING_VALUES.date_value);
    // CANNOT SET // set_input_value_by_id(ID_WHERE_VALUE_FILE, STARTING_VALUES.file_value);
    // "Uncaught InvalidStateError: Failed to set the 'value' property on 'HTMLInputElement': This input element accepts a filename, which may only be programmatically set to the empty string."
    set_input_value_by_id(ID_WHERE_VALUE_FLOAT, STARTING_VALUES.float_value);
    set_input_value_by_id(ID_WHERE_VALUE_INTEGER, STARTING_VALUES.int_value);
    set_input_value_by_id(ID_WHERE_VALUE_TEXT, STARTING_VALUES.string_value);
    set_hidden_boolean_input_by_id(ID_OFFER_WHERE, STARTING_VALUES.offer_where);
    warn(STARTING_VALUES.form_errors); // will be empty if all OK
    // announce("Loaded!");
}
