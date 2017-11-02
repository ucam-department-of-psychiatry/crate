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
    // QB_DATATYPE_* values must match crate_anon.common.sql.py
var QB_DATATYPE_DATE = "date",
    QB_DATATYPE_FLOAT = "float",
    QB_DATATYPE_INTEGER = "int",
    QB_DATATYPE_STRING = "string",
    QB_DATATYPE_STRING_FULLTEXT = "string_fulltext",
    QB_DATATYPE_UNKNOWN = "unknown",
    DIALECT_MYSQL = "mysql",  // must match sql_grammar.py
    DIALECT_MSSQL = "mssql",  // must match sql_grammar.py
    // All ID_* values must match HTML id tags.
    // ID_ANNOUNCEMENT = "id_announcement",
    ID_COLTYPE = "id_coltype",
    ID_COLTYPE_INFO = "id_coltype_info",
    ID_COLUMN_PICKER = "id_column",
    ID_COMMENT = "id_comment",
    ID_CURRENT_COLUMN = "id_current_column",
    ID_DATABASE_PICKER = "id_database",
    ID_SCHEMA_PICKER = "id_schema",
    ID_TABLE_PICKER = "id_table",
    ID_OFFER_WHERE = "id_offer_where",
    ID_SELECT_BUTTON = "id_select_button",
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
    // Both MySQL and SQL Server permit != or <> for "not equal",
    // but <> is the ANSI standard
    OPS_NUMBER_DATE = [
        {value: "<", text: "<"},
        {value: "<=", text: "<="},
        {value: "=", text: "="},
        {value: "<>", text: "<> (not equal)"},
        {value: ">=", text: ">="},
        {value: ">", text: ">"}
    ].concat(OPS_IN_NULL),
    OPS_STRING = [  // any string field, any dialect
        {value: "=", text: "="},
        {value: "<>", text: "<> (not equal)"},
        {value: "LIKE", text: "LIKE (use % _ as wildcards)"}
    ].concat(OPS_IN_NULL),
    OPS_STRING_MYSQL = OPS_STRING.concat([
        {value: "REGEXP", text: "REGEXP (regular expression match)"}
    ]),
    OPS_STRING_FULLTEXT_MYSQL = OPS_STRING_MYSQL.concat([
        {value: "MATCH", text: "MATCH (match whole words)"}
    ]),
    OPS_STRING_FULLTEXT_MSSQL = OPS_STRING.concat([
        {value: "CONTAINS", text: "CONTAINS (match whole words)"}
    ]),
    OPS_USING_FILE = ["IN", "NOT IN"],
    OPS_USING_NULL = ["IS NULL", "IS NOT NULL"];

// The variables that follow are pre-populated by the server.
// See query_build.html and research/views.py
// The declarations from the server come later in the HTML and will override
// these, so it's safe to declare dummy instances here, which helps the linter:

var DATABASE_STRUCTURE = [
        {
            database: 'dummy_database',
            schema: 'dummy_schema',
            tables: [
                {
                    table: 'dummy_table',
                    columns: [
                        {
                            colname: 'dummy_column',
                            coltype: QB_DATATYPE_STRING,
                            rawtype: 'VARCHAR(255)',
                            comment: 'dummy_comment'
                        }
                    ]
                }
            ]
        }
    ],
    STARTING_VALUES = {
        'database': '',
        'schema': '',
        'table': '',
        'column': '',
        'op': '',
        'date_value': '',
        'float_value': '',
        'int_value': '',
        'string_value': '',
        'offer_where': false,
        'form_errors': '',
        'default_database': '',
        'default_schema': '',
        'with_database': false
    },
    SQL_DIALECT = DIALECT_MYSQL;

// ============================================================================
// Javascript helpers
// ============================================================================

function contains(a, obj) {
    for (var i = 0; i < a.length; i++) {
        if (a[i] === obj) {
            return true;
        }
    }
    return false;
}

// ============================================================================
// Read table/column information from variables passed in
// ============================================================================

function get_all_db_names() {
    var db_names = [],
        db,
        i;
    for (i = 0; i < DATABASE_STRUCTURE.length; ++i) {
        db = DATABASE_STRUCTURE[i].database;
        if (!contains(db_names, db)) {
            db_names.push(db);
        }
    }
    return db_names;
}

function get_all_schema_names(db) {
    var schema_names = [],
        schema,
        i;
    for (i = 0; i < DATABASE_STRUCTURE.length; ++i) {
        if (DATABASE_STRUCTURE[i].database === db) {
            schema = DATABASE_STRUCTURE[i].schema;
            if (!contains(schema_names, schema)) {
                schema_names.push(schema);
            }
        }
    }
    return schema_names;
}

function get_schema_info(db, schema) {
    var i;
    for (i = 0; i < DATABASE_STRUCTURE.length; ++i) {
        if (DATABASE_STRUCTURE[i].database === db &&
                DATABASE_STRUCTURE[i].schema === schema) {
            return DATABASE_STRUCTURE[i];
        }
    }
    return null;
}

function get_all_table_names(db, schema) {
    var schema_info = get_schema_info(db, schema),
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

function get_table_info(db, schema, table) {
    var schema_info = get_schema_info(db, schema),
        i;
    if (schema_info === null) {
        return null;
    }
    for (i = 0; i < schema_info.tables.length; ++i) {
        if (schema_info.tables[i].table === table) {
            return schema_info.tables[i];
        }
    }
    return null;
}

function get_all_column_names(db, schema, table) {
    var tableinfo = get_table_info(db, schema, table),
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

function get_column_info(db, schema, table, column) {
    var tableinfo = get_table_info(db, schema, table),
        i;
    if (tableinfo === null) {
        return null;
    }
    for (i = 0; i < tableinfo.columns.length; ++i) {
        if (tableinfo.columns[i].colname === column) {
            return tableinfo.columns[i];
        }
    }
}

// ============================================================================
// Ancillary and HTML/DOM manipulation functions
// ============================================================================

// noinspection JSUnusedLocalSymbols
function log(text) {
    // console.log(text);
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
    if (!unsafe) {
        return '';
    }
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
            if (element.options[i].value === value) {
                element.selectedIndex = i;
                return;
            }
        }
    } else if (default_value) {
        for (i = 0; i < element.options.length; ++i) {
            if (element.options[i].value === default_value) {
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

/*
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
*/

function set_hidden_boolean_input_by_id(id, value) {
    set_input_value_by_id(id, value ? "True" : "False");
}

function display_html_by_id(element_id, html, append, sep) {
    append = append === undefined ? false : append;
    sep = sep === undefined ? "<br>" : sep;
    var element = document.getElementById(element_id);
    if (append) {
        if (element.innerHTML) {
            element.innerHTML += sep;
        }
        element.innerHTML += html;
    } else {
        element.innerHTML = html;
    }
}

function warn(html) {
    log("WARNING: " + html);
    display_html_by_id(ID_WARNING, html, true);
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

function get_current_db() {
    if (STARTING_VALUES.with_database) {
        return get_picker_value_by_id(ID_DATABASE_PICKER);
    } else {
        return '';
    }
}

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

function set_db(db) {
    set_picker_value_by_id(ID_DATABASE_PICKER, db);
    db_changed();
}

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
    log("where_op_changed: coltype = " + coltype + ", op = " + op);
    hide_input(entry_date);
    hide_input(entry_file);
    hide_input(entry_float);
    hide_input(entry_integer);
    hide_input(entry_text);
    if (!STARTING_VALUES.offer_where || !op) {
        return;
    }
    if (OPS_USING_FILE.indexOf(op) !== -1) {
        show_input(entry_file);
    } else if (OPS_USING_NULL.indexOf(op) !== -1) {
        // show nothing
    } else {
        switch (coltype) {
            case QB_DATATYPE_DATE:
                show_input(entry_date);
                break;
            case QB_DATATYPE_FLOAT:
                show_input(entry_float);
                break;
            case QB_DATATYPE_INTEGER:
                show_input(entry_integer);
                break;
            case QB_DATATYPE_STRING:
            case QB_DATATYPE_STRING_FULLTEXT:
                show_input(entry_text);
                break;
            case QB_DATATYPE_UNKNOWN:
                break;
            default:
                break;
        }
    }
}

function column_changed() {
    var where_op_picker = document.getElementById(ID_WHERE_OP),
        where_button = document.getElementById(ID_WHERE_BUTTON),
        select_button = document.getElementById(ID_SELECT_BUTTON),
        db = get_current_db(),
        schema = get_current_schema(),
        table = get_current_table(),
        column = get_current_column(),
        colinfo = get_column_info(db, schema, table, column),
        old_op = get_current_op(),
        coltype = colinfo ? colinfo.coltype : null,
        rawtype = colinfo ? colinfo.rawtype : null,
        comment = colinfo ? colinfo.comment : null,
        colinfo_html = "";
    log("column_changed: column = " + column + ", coltype = " + coltype);
    set_input_value_by_id(ID_COLTYPE, coltype);
    if (STARTING_VALUES.with_database) {
        colinfo_html += "<i>" + db + "</i>.";
    }
    colinfo_html += "<i>" + schema + "</i>." +
                    table + "." +
                    "<b>" + column + "</b>";
    display_html_by_id(ID_CURRENT_COLUMN, colinfo_html);
    display_html_by_id(
        ID_COMMENT,
        ("<i>" + escapeHtml(comment) + "</i>") || "&nbsp;");
    display_html_by_id(
        ID_COLTYPE_INFO,
        "Type: " + coltype + " (SQL type: " + rawtype + ")");
    if (!column) {
        hide_element(select_button);
    } else {
        show_element(select_button);
    }
    if (!STARTING_VALUES.offer_where || !column ||
            coltype === QB_DATATYPE_UNKNOWN) {
        reset_select_options(where_op_picker, OPS_NONE);
        hide_element(where_op_picker);
        hide_element(where_button);
    } else {
        switch (coltype) {
            case QB_DATATYPE_DATE:
            case QB_DATATYPE_FLOAT:
            case QB_DATATYPE_INTEGER:
                reset_select_options(where_op_picker, OPS_NUMBER_DATE);
                break;
            case QB_DATATYPE_STRING:
                if (SQL_DIALECT === DIALECT_MYSQL) {
                    reset_select_options(where_op_picker, OPS_STRING_MYSQL);
                } else {
                    reset_select_options(where_op_picker, OPS_STRING);
                }
                break;
            case QB_DATATYPE_STRING_FULLTEXT:
                if (SQL_DIALECT === DIALECT_MYSQL) {
                    reset_select_options(where_op_picker,
                                         OPS_STRING_FULLTEXT_MYSQL);
                } else if (SQL_DIALECT === DIALECT_MSSQL) {
                    reset_select_options(where_op_picker,
                                         OPS_STRING_FULLTEXT_MSSQL);
                } else {
                    warn("Error: unknown SQL dialect " + SQL_DIALECT +
                         "; fulltext search ignored");
                    reset_select_options(where_op_picker, OPS_STRING);
                }
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
    var db = get_current_db(),
        schema = get_current_schema(),
        table = get_current_table(),
        column_picker = document.getElementById(ID_COLUMN_PICKER),
        column_names = get_all_column_names(db, schema, table),
        column_options = get_select_options_from_list(column_names);
    log("table_changed: table = " + table);
    if (!table) {
        hide_element(column_picker);
    } else {
        show_element(column_picker);
    }
    reset_select_options_by_id(ID_COLUMN_PICKER, column_options);
    column_changed();
}

function schema_changed() {
    var db = get_current_db(),
        schema = get_current_schema(),
        table_picker = document.getElementById(ID_TABLE_PICKER),
        table_names = get_all_table_names(db, schema),
        table_options = get_select_options_from_list(table_names);
    log("schema_changed: schema = " + schema);
    if (!schema) {
        hide_element(table_picker);
    } else {
        show_element(table_picker);
    }
    reset_select_options_by_id(ID_TABLE_PICKER, table_options);
    table_changed();
}

function db_changed() {
    var db = get_current_db(),
        schema_picker = document.getElementById(ID_SCHEMA_PICKER),
        schema_names = get_all_schema_names(db),
        schema_options = get_select_options_from_list(schema_names);
    log("db_changed: db = " + db);
    if (!db) {
        hide_element(schema_picker);
    } else {
        show_element(schema_picker);
    }
    reset_select_options_by_id(ID_SCHEMA_PICKER, schema_options);
    schema_changed();
}

function populate() {
    // This is the "onload" function called by the HTML.
    log("populate");
    var db_picker = document.getElementById(ID_DATABASE_PICKER),
        schema_picker = document.getElementById(ID_SCHEMA_PICKER),
        table_picker = document.getElementById(ID_TABLE_PICKER),
        column_picker = document.getElementById(ID_COLUMN_PICKER),
        where_op_picker = document.getElementById(ID_WHERE_OP),
        coltype_info_element = document.getElementById(ID_COLTYPE_INFO),
        current_col_element = document.getElementById(ID_CURRENT_COLUMN),
        db_names = get_all_db_names(),
        db_options = get_select_options_from_list(db_names),
        schema_names = get_all_schema_names(''),  // in case we're not using the database level
        schema_options = get_select_options_from_list(schema_names),  // in case we're not using the database level
        some_info = (STARTING_VALUES.with_database
                     ? db_names.length > 0
                     : schema_names.length > 0);
    if (STARTING_VALUES.with_database) {
        db_picker.addEventListener("change", db_changed);
    }
    schema_picker.addEventListener("change", schema_changed);
    table_picker.addEventListener("change", table_changed);
    column_picker.addEventListener("change", column_changed);
    where_op_picker.addEventListener("change", where_op_changed);
    if (some_info) {
        if (STARTING_VALUES.with_database) {
            reset_select_options(db_picker, db_options);
            set_db(STARTING_VALUES.database);
        } else {
            hide_element(db_picker);
            reset_select_options(schema_picker, schema_options);
        }
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
    } else {
        warn("No databases/schemas!");
        hide_element(db_picker);
        hide_element(schema_picker);
        hide_element(table_picker);
        hide_element(column_picker);
        hide_element(where_op_picker);
        hide_element(current_col_element);
        hide_element(coltype_info_element);
    }
    if (STARTING_VALUES.form_errors) {  // will be empty if all OK
        warn(STARTING_VALUES.form_errors);
    }
    // announce("Loaded!");
}
