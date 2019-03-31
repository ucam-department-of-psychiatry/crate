/*

CrateGatePipeline.java
    -- note that javac wants the file to have the same name as its class
    http://docstore.mik.ua/orelly/java-ent/jnut/ch02_12.htm
    http://www.cs.usfca.edu/~parrt/course/601/lectures/java.tools.html

Based on

- https://gate.ac.uk/wiki/code-repository/src/sheffield/examples/StandAloneAnnie.java

     *  StandAloneAnnie.java
     *
     *
     * Copyright (c) 2000-2001, The University of Sheffield.
     *
     * This file is part of GATE (see http://gate.ac.uk/), and is free
     * software, licenced under the GNU Library General Public License,
     * Version 2, June1991.
     *
     * A copy of this licence is included in the distribution in the file
     * licence.html, and is also available at http://gate.ac.uk/gate/licence.html.
     *
     *  hamish, 29/1/2002
     *
     *  $Id: StandAloneAnnie.java,v 1.6 2006/01/09 16:43:22 ian Exp $

      Copyright (C) 2000-2001, The University of Sheffield.

- https://gate.ac.uk/wiki/code-repository/src/sheffield/examples/BatchProcessApp.java

     *  BatchProcessApp.java
     *
     *
     * Copyright (c) 2006, The University of Sheffield.
     *
     * This file is part of GATE (see http://gate.ac.uk/), and is free
     * software, licenced under the GNU Library General Public License,
     * Version 2, June1991.
     *
     * A copy of this licence is included in the distribution in the file
     * licence.html, and is also available at http://gate.ac.uk/gate/licence.html.
     *
     *  Ian Roberts, March 2006
     *
     *  $Id: BatchProcessApp.java,v 1.5 2006/06/11 19:17:57 ian Exp $

- https://gate.ac.uk/sale/tao/splitch7.html#chap:api

- New code/derivative work (noting that the GPLv3+ license is compatible with
  the inclusion of code already licensed under the LGPLv2; see
  https://www.gnu.org/licenses/gpl-faq.html#AllCompatibility):
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

TO COMPILE, THEN RUN: see buildme.sh

FIELDS THAT ARE USED AS STANDARD: see processAnnotation()

*/

// no "package" command required

import java.util.*;
import java.io.*;
import java.text.SimpleDateFormat;

import org.apache.log4j.ConsoleAppender;
import org.apache.log4j.Level;
import org.apache.log4j.Logger;
import org.apache.log4j.PatternLayout;

import gate.Annotation;
import gate.AnnotationSet;
import gate.Corpus;
import gate.CorpusController;
import gate.Document;
import gate.Factory;
import gate.FeatureMap;
import gate.Gate;

import gate.corpora.RepositioningInfo;
import gate.creole.ExecutionException;
import gate.creole.ResourceInstantiationException;
import gate.util.GateException;
import gate.util.InvalidOffsetException;
import gate.util.persistence.PersistenceManager;

/**
 * CrateGatePipeline is a command-line program that fires up a specific GATE
 * app, reads text from stdin, sends it to GATE, and prints the results to
 * stdout.
 */

public class CrateGatePipeline {

    // ========================================================================
    // Members
    // ========================================================================

    // Constants
    private static final String m_default_input_terminator = "END_OF_DOCUMENT";
    private static final String m_default_output_terminator = "END_OF_DOCUMENT";
    private static final String TAB = "\t";
    private static final String NEWLINE = "\n";
    // Interface
    private String m_args[];
    // Options
    private ArrayList<String> m_target_annotations = new ArrayList<String>();
    private String m_input_terminator = m_default_input_terminator;
    private String m_output_terminator = m_default_output_terminator;
    private File m_gapp_file = null;
    private String m_file_encoding = null;  // null: use system default
    private int m_verbose = 0;
    private String m_annotxml_filename_stem = null;
    private String m_gatexml_filename_stem = null;
    private String m_tsv_filename_stem = null;
    private boolean m_suppress_gate_stdout = false;
    private boolean m_show_contents_on_crash = false;
    private boolean m_continue_on_crash = false;
    private ArrayList<String> m_set_inclusion_list = new ArrayList<String>();
    private ArrayList<String> m_set_exclusion_list = new ArrayList<String>();
    private Map<String, ArrayList<String>> m_set_annotation_combos =
        new HashMap<String, ArrayList<String>>();
    // Text
    private static final String m_sep1 = ">>>>>>>>>>>>>>>>> ";
    private static final String m_sep2 = "<<<<<<<<<<<<<<<<<";
    // Internal
    private String m_extra_log_prefix = "";
    private int m_count = 0;
    private String m_pipe_encoding = "UTF-8";
    private PrintStream m_out = null;
    private String m_current_contents_for_crash_debugging = null;
    private boolean m_output_terminator_pending = false;
    // Logger:
    private static final Logger m_log = Logger.getLogger(CrateGatePipeline.class);

    // GATE things
    private CorpusController m_controller = null;
    private Corpus m_corpus = null;

    // Output keys
    private static final String KEY_SET = "_set";
    private static final String KEY_TYPE = "_type";
    private static final String KEY_ID = "_id";
    private static final String KEY_STARTPOS = "_start";
    private static final String KEY_ENDPOS = "_end";
    private static final String KEY_CONTENT = "_content";

    // ========================================================================
    // Constructor
    // ========================================================================

    /** Process command-line arguments and execute the pipeline. */

    public CrateGatePipeline(String args[]) throws GateException, IOException {
        // --------------------------------------------------------------------
        // Arguments
        // --------------------------------------------------------------------
        m_args = args;
        processArgs();

        // --------------------------------------------------------------------
        // Logging
        // --------------------------------------------------------------------
        // http://stackoverflow.com/questions/8965946/configuring-log4j-loggers-programmatically
        // https://logging.apache.org/log4j/1.2/apidocs/org/apache/log4j/PatternLayout.html
        Level main_level = m_verbose >= 2 ? Level.DEBUG
                                          : (m_verbose >= 1 ? Level.INFO
                                                            : Level.WARN);
        Level gate_level = m_verbose >= 3 ? Level.DEBUG
                                          : (m_verbose >= 2 ? Level.INFO
                                                            : Level.WARN);
        String tag = "";
        if (!m_extra_log_prefix.isEmpty()) {
            tag += "|" + escapePercent(m_extra_log_prefix);
        }
        String log_pattern = "%d{yyyy-MM-dd HH:mm:ss.SSS} [%p|%c" + tag + "] %m%n";
        PatternLayout log_layout = new PatternLayout(log_pattern);
        ConsoleAppender log_appender = new ConsoleAppender(log_layout, "System.err");
        Logger rootlog = Logger.getRootLogger();
        rootlog.addAppender(log_appender);

        rootlog.setLevel(gate_level);
        m_log.setLevel(main_level);

        /*
        // Test:
        rootlog.debug("rootlog debug");
        rootlog.info("rootlog info");
        rootlog.warn("rootlog warn");
        m_log.debug("m_log debug");
        m_log.info("m_log info");
        m_log.warn("m_log warn");
        */

        // --------------------------------------------------------------------
        // Setup stdout
        // --------------------------------------------------------------------

        // We're going to write to this:
        m_out = new PrintStream(System.out, true, m_pipe_encoding);

        // Some GATE apps may write to System.out, which will cause us problems
        // unless we divert them:
        if (m_suppress_gate_stdout) {
            // http://stackoverflow.com/questions/4799006
            m_log.debug("Suppressing GATE stdout");
            System.setOut(new PrintStream(new OutputStream() {
                public void write(int b) {
                    // DO NOTHING
                }
            }));
        } else {
            m_log.debug("Sending GATE stdout to stderr");
            System.setOut(System.err);
        }

        // Report arguments etc.

        reportArgs(true);
        // Sets:
        if (m_set_inclusion_list.size() == 0) {
            m_log.debug("Including all sets by default");
        } else {
            for (String include : m_set_inclusion_list) {
                m_log.debug("Explicitly including set: " + toPrintable(include));
            }
        }
        for (String exclude : m_set_exclusion_list) {
            m_log.debug("Explicitly excluding set: " + toPrintable(exclude));
        }
        // Annotations:
        if (!m_set_annotation_combos.isEmpty()) {
            for (Map.Entry<String, ArrayList<String>> entry :
                    m_set_annotation_combos.entrySet()) {
                String set = entry.getKey();
                ArrayList<String> annots = entry.getValue();
                for (String annot : annots) {
                    m_log.debug("Including set = " + toPrintable(set) +
                                ", annotation = " + toPrintable(annot));
                }
            }
        } else {
            if (m_target_annotations.isEmpty()) {
                m_log.debug("Including all annotations by default");
            } else {
                for (String annot : m_target_annotations) {
                    m_log.debug("Including annotation: " + toPrintable(annot));
                }
            }
        }

        // --------------------------------------------------------------------
        // Do interesting things
        // --------------------------------------------------------------------
        // - We need to be able to handle GATE crashes.
        // - That requires us to restart GATE, so we need the exception-catcher
        //   to be above the code that calls setupGate() as well as the code
        //   that processes input.
        // - That means here, above runPipeline().
        // - If we're going to crash out, it's easy -- but if we're going to
        //   continue, we are likely to need to write the output terminator
        //   for the failed record first.

        boolean finished = false;
        while (!finished) {
            try {
                runPipeline();
                finished = true;
            } catch (GateException | RuntimeException e) {
                // GateException: "sensible" exception
                //
                // RuntimeException: likely bug in GATE code
                // ... e.g. IllegalArgumentException; see
                // https://docs.oracle.com/javase/7/docs/api/java/lang/RuntimeException.html

                m_log.error("GATE exception; aborting; stack trace follows");
                reportException(e);
                if (m_continue_on_crash) {
                    m_log.warn("Proceeding despite GATE crash as requested");
                    if (m_output_terminator_pending) {
                        writeOutputTerminator();
                    }
                } else {
                    // Die explicitly with a defined exit code -- otherwise, Java
                    // exits with an UNDEFINED (e.g. 0 = "happy") return code.
                    abort();
                }
            } catch (Exception e) {
                m_log.error("Generic exception; aborting; stack trace follows");
                reportException(e);
                abort();  // as above
            }
        }
        m_log.info("Finished.");
        exit();
    }

    /**
     * Report an exception to stderr, +/- the text that caused the crash.
     */

    private void reportException(Exception e) {
        e.printStackTrace();  // always goes to System.err (stderr)
        if (m_show_contents_on_crash) {
            if (m_current_contents_for_crash_debugging == null) {
                m_log.error("No current contents");
            } else {
                m_log.error("Current contents being processed:");
                writeStderr(m_current_contents_for_crash_debugging);
            }
        }
    }

    /**
     * Run a GATE pipeline; read text from stdin; send it to GATE; write
     * results to stdout.
     */

    private void runPipeline() throws GateException, IOException {
        setupGate();
        m_log.info("Ready for input");

        // Read from stdin, using end-of-text markers to split stdin into
        // multiple texts, creating documents in turn
        StdinResult result;
        do {
            // Read from stdin
            result = readStdin();
            if (result.finished) {
                continue;
            }
            m_log.info("Text read from stdin");
            m_log.debug(m_sep1 + "CONTENTS OF STDIN:");
            m_log.debug(result.contents);
            m_log.debug(m_sep2);
            m_output_terminator_pending = true;  // in case of GATE crash

            // Process text
            processInput(result.contents);

            ++m_count;
        } while (!result.finished);
    }

    // ========================================================================
    // Handling of args, exiting, etc.
    // ========================================================================

    /** Exit in a happy way. */

    private void exit() {
        System.exit(0);
    }

    /** Exit in a sad way. */

    private void abort() {
        System.exit(1);
    }

    /** Complain that the user has passed bad command-line arguments. Exit. */

    private void argfail(String msg) {
        // Don't use the log; it's not configured yet.
        writeStderr(msg);
        reportArgs(false);
        abort();
    }

    /** Show a usage message. */

    private void usage() {
        writeStderr(
"usage: CrateGatePipeline -g GATEAPP [-a ANN [-a ANN [...]]]\n" +
"                         [--include_set SET [--include_set SET [...]]]\n" +
"                         [--exclude_set SET [--exclude_set SET [...]]]\n" +
"                         [-e ENCODING] [-it TERM] [-ot TERM] [-lt LOGTAG]\n" +
"                         [-wa FILESTEM] [-wg FILESTEM] [-wt FILESTEM]\n" +
"                         [-s] [--show_contents_on_crash]\n" +
"                         [-h] [-v [-v [-v]]]\n" +
"\n" +
"Java front end to GATE natural language processor.\n" +
"\n" +
"- Takes input on stdin. Produces output on stdout.\n" +
"- GATE applications produce output clustered (1) into named annotation sets\n" +
"  (with a default, unnamed set). (2) Within annotation sets, we find\n" +
"  annotations. (3) Each annotation is a collection of key/value pairs.\n" +
"  This collection is not fixed, in that individual annotations, or keys within\n" +
"  annotations, may be present sometimes and absent sometimes, depending on the\n" +
"  input text.\n" +
"\n" +
"Required arguments:\n" +
"\n" +
"  --gate_app GATEAPP\n" +
"  -g GATEAPP\n" +
"                   Specifies the GATE app (.gapp/.xgapp) file to use.\n" +
"\n" +
"Optional arguments:\n" +
"\n" +
"  --include_set SET\n" +
"  --exclude_set SET\n" +
"                   Includes or excludes the specified GATE set, by name.\n" +
"                   By default, the inclusion list is empty, and the exclusion\n" +
"                   list is also empty. By specifying set names here, you add\n" +
"                   to the inclusion or exclusion list. You can specify each\n" +
"                   option multiple times. Then, the rules are as follows:\n" +
"                   the output from a GATE set is included if (A) the inclusion\n" +
"                   list is empty OR the set is on the inclusion list, AND (B)\n" +
"                   the set is not on the exclusion list. Note also that there\n" +
"                   is a default set with no name; refer to this one using\n" +
"                   the empty string \"\". Set names are compared in a\n" +
"                   case-sensitive manner.\n" +
"\n" +
"  --annotation ANNOT\n" +
"  -a ANNOT\n" +
"                   Adds the specified annotation to the target list.\n" +
"                   If you don't specify any, you'll get them all.\n" +
"\n" +
"  --set_annotation SET ANNOT\n" +
"  -sa SET ANNOT\n" +
"                   Adds the specific set/annotation combination to the target\n" +
"                   list. Use this option for maximum control. You cannot mix\n" +
"                   --annotation and --set_annotation.\n" +
"\n" +
"  --encoding ENCODING\n" +
"  -e ENCODING\n" +
"                   The character encoding of the source documents, to be used\n" +
"                   for file output. If not specified, the platform default\n" +
"                   encoding (currently \"" + System.getProperty("file.encoding") + "\") is assumed.\n" +
"\n" +
"  --input_terminator TERMINATOR\n" +
"  -it TERMINATOR\n" +
"                   Specify stdin end-of-document terminator.\n" +
"\n" +
"  --output_terminator TERMINATOR\n" +
"  -ot TERMINATOR\n" +
"                   Specify stdout end-of-document terminator.\n" +
"\n" +
"  --log_tag LOGTAG\n" +
"  -lt LOGTAG\n" +
"                   Use an additional tag for stderr logging.\n" +
"                   Helpful in multiprocess environments.\n" +
"\n" +
"  --write_annotated_xml FILESTEM\n" +
"  -wa FILESTEM\n" +
"                   Write annotated XML document to FILESTEM<n>.xml, where <n>\n" +
"                   is the file's sequence number (starting from 0).\n" +
"\n" +
"  --write_gate_xml FILESTEM\n" +
"  -wg FILESTEM\n" +
"                   Write GateXML document to FILESTEM<n>.xml.\n" +
"\n" +
"  --write_tsv FILESTEM\n" +
"  -wt FILESTEM\n" +
"                   Write TSV-format annotations to FILESTEM<n>.tsv.\n" +
"\n" +
"  --suppress_gate_stdout\n" +
"  -s\n" +
"                   Suppress any stdout from GATE application.\n" +
"\n" +
"  --show_contents_on_crash\n" +
"  -show_contents_on_crash\n" +
"                   If GATE crashes, report the current text to stderr (as well\n" +
"                   as reporting the error).\n" +
"                   (WARNING: likely to contain identifiable material.)\n" +
"\n" +
"  --continue_on_crash\n" +
"  -c\n" +
"                   If GATE crashes, carry on after reporting the error.\n" +
"\n" +
"  --help\n" +
"  -h\n" +
"                   Show this help message and exit.\n" +
"\n" +
"  --verbose\n" +
"  -v\n" +
"                   Verbose (use up to 3 times to be more verbose).\n"
        );
    }

    /**
     * Process command-line arguments from m_args, and set internal variables.
     */

    private void processArgs() {
        int i = 0;
        int nleft;
        String arg;
        String insufficient = "CrateGatePipeline: Insufficient arguments while processing ";
        // Process
        while (i < m_args.length) {
            arg = m_args[i++].toLowerCase();
            nleft = m_args.length - i;
            switch (arg) {
                case "--include_set":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_set_inclusion_list.add(m_args[i++]);
                    break;

                case "--exclude_set":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_set_exclusion_list.add(m_args[i++]);
                    break;

                case "-a":
                case "--annotation":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_target_annotations.add(m_args[i++]);
                    break;

                case "-sa":
                case "--set_annotation":
                    {
                        if (nleft < 2) argfail(insufficient + arg);
                        String set = m_args[i++];
                        String annot = m_args[i++];
                        ArrayList<String> annotlist = m_set_annotation_combos.get(set);
                        if (annotlist == null) {
                            annotlist = new ArrayList<String>();
                            annotlist.add(annot);
                            m_set_annotation_combos.put(set, annotlist);
                        } else {
                            if (!annotlist.contains(annot)) {
                                annotlist.add(annot);
                            }
                        }
                    }
                    break;

                case "-e":
                case "--encoding":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_file_encoding = m_args[i++];
                    break;

                case "-g":
                case "--gate_app":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_gapp_file = new File(m_args[i++]);
                    break;

                case "-h":
                case "--help":
                    usage();
                    exit();
                    break;

                case "-it":
                case "--input_terminator":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_input_terminator = m_args[i++];
                    break;

                case "-ot":
                case "--output_terminator":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_output_terminator = m_args[i++];
                    break;

                case "-lt":
                case "--log_tag":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_extra_log_prefix = m_args[i++];
                    break;

                case "-v":
                case "--verbose":
                    m_verbose++;
                    break;

                case "-wa":
                case "--write_annotated_xml":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_annotxml_filename_stem = m_args[i++];
                    break;

                case "-wg":
                case "--write_gate_xml":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_gatexml_filename_stem = m_args[i++];
                    break;

                case "-wt":
                case "--write_tsv":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_tsv_filename_stem = m_args[i++];
                    break;

                case "-s":
                case "--suppress_gate_stdout":
                    m_suppress_gate_stdout = true;
                    break;

                case "-show_contents_on_crash":
                case "--show_contents_on_crash":
                    m_show_contents_on_crash = true;
                    break;

                case "-c":
                case "--continue_on_crash":
                    m_continue_on_crash = true;
                    break;

                default:
                    usage();
                    abort();
                    break;
            }
        }
        // Validate
        if (m_gapp_file == null) {
            argfail("Missing -g parameter (no .gapp file specified); " +
                    "use -h for help");
            abort();
        }
        if (!m_target_annotations.isEmpty() && !m_set_annotation_combos.isEmpty()) {
            argfail("Use either --annotation or --set_annotation, not both.");
            abort();
        }
    }

    /** Report command-line arguments (from m_args). */

    private void reportArgs(boolean to_log) {
        for (int i = 0; i < m_args.length; i++) {
            String s = "Arg " + i + " = " + m_args[i];
            if (to_log) {
                m_log.debug(s);
            } else {
                writeStderr(s);
            }
        }
    }

    // ========================================================================
    // Escaping text
    // ========================================================================

    /** Escape tabs and newlines with backslash-escaping. */

    private String escapeTabsNewlines(String s) {
        if (s == null) {
            return s;
        }
        s = s.replace("\\", "\\");
        s = s.replace("\n", "\\n");
        s = s.replace("\r", "\\r");
        s = s.replace("\t", "\\t");
        return s;
    }

    /**
     * Escape % to %% (to avoid log strings being interpreted as format
     * strings).
     */

    private String escapePercent(String s) {
        if (s == null) {
            return s;
        }
        s = s.replace("%", "%%");
        return s;
    }

    private static final char CONTROL_LIMIT = ' ';
    private static final char PRINTABLE_LIMIT = '\u007e';
    private static final char[] HEX_DIGITS = new char[] { '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f' };

    /** Create an escaped representation of a string, for debugging. */

    public static String toPrintable(String source) {
        // https://stackoverflow.com/questions/1350397/java-equivalent-of-python-repr
        if (source == null) {
            return null;
        } else {
            final StringBuilder sb = new StringBuilder();
            final int limit = source.length();
            char[] hexbuf = null;
            int pointer = 0;

            sb.append('"');
            while (pointer < limit) {
                int ch = source.charAt(pointer++);
                switch (ch) {
                case '\0': sb.append("\\0"); break;
                case '\t': sb.append("\\t"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                default:
                    if (CONTROL_LIMIT <= ch && ch <= PRINTABLE_LIMIT) {
                        sb.append((char)ch);
                    } else {
                        sb.append("\\u");
                        if (hexbuf == null) {
                            hexbuf = new char[4];
                        }
                        for (int offs = 4; offs > 0; ) {
                            hexbuf[--offs] = HEX_DIGITS[ch & 0xf];
                            ch >>>= 4;
                        }
                        sb.append(hexbuf, 0, 4);
                    }
                }
            }
            return sb.append('"').toString();
        }
    }

    // ========================================================================
    // stdin handling
    // ========================================================================

    /**
      * Represents a single input text read from stdin, and whether we have
      * seen the "please end" special string and therefore are completely
      * finished. Returned by readStdin().
      */

    private final class StdinResult {
        public String contents;
        public boolean finished;
        StdinResult(String contents, boolean finished) {
            this.contents = contents;
            this.finished = finished;
        }
        StdinResult() {
            this.contents = null;
            this.finished = false;
        }
    }

    /**
     * Read from stdin until we receive a terminator (either "end of this
     * string" or "end of all strings" and return a StdinResult object.
     */

    private StdinResult readStdin() throws IOException {
        BufferedReader br = new BufferedReader(
            new InputStreamReader(System.in, m_pipe_encoding));
        StringBuffer sb = new StringBuffer();
        String line;
        boolean finished_this = false;
        boolean finished_everything = false;
        while (!finished_this) {
            line = br.readLine();
            if (line == null) {  // end of stdin
                finished_this = true;
                finished_everything = true;
            } else if (line.equals(m_input_terminator)) {  // end of this input
                finished_this = true;
            } else {
                sb.append(line);
                sb.append("\n");
            }
        }
        return new StdinResult(sb.toString(), finished_everything);
    }

    // ========================================================================
    // stdout/stderr/log handling
    // ========================================================================

    /** Write a message to stderr. */

    private void writeStderr(String msg) {
        System.err.println(msg);
    }

    /** Write a message to stdout. */

    private void print(String msg) {
        m_out.print(msg);
    }

    /** Write a message to stdout and line-terminate it. */

    private void println(String msg) {
        m_out.println(msg);
    }

    // ========================================================================
    // File handling
    // ========================================================================

    /** Write text to a file. */

    private void writeToFile(String filename, String contents)
            throws FileNotFoundException, UnsupportedEncodingException,
            IOException {
        File file = new File(filename);
        FileOutputStream fos = new FileOutputStream(file);
        BufferedOutputStream bos = new BufferedOutputStream(fos);
        OutputStreamWriter out;
        if (m_file_encoding == null) {
            out = new OutputStreamWriter(bos);
        } else {
            out = new OutputStreamWriter(bos, m_file_encoding);
        }
        out.write(contents);
        out.close();
    }

    /** Write XML to a file, naming it according to m_count. */

    private void writeXml(String stem, String xml)
            throws FileNotFoundException, UnsupportedEncodingException,
            IOException {
        String filename = stem + m_count + ".xml";
        writeToFile(filename, xml);
    }

    // ========================================================================
    // GATE input processing
    // ========================================================================

    /** Initialize GATE. */

    private void setupGate() throws GateException, IOException {
        m_log.info("Initializing GATE...");
        Gate.init();
        m_log.info("... GATE initialized");

        m_log.info("Initializing app...");
        // load the saved application
        m_controller = (CorpusController)
            PersistenceManager.loadObjectFromFile(m_gapp_file);
        m_log.info("... app initialized");

        m_log.info("Initializing corpus...");
        // Create a GATE corpus (name is arbitrary)
        m_corpus = Factory.newCorpus("CrateGatePipeline corpus");  // throws ResourceInstantiationException
        // Tell the controller about the corpus
        m_controller.setCorpus(m_corpus);  // doesn't throw
        m_log.info("... corpus initialized");
    }

    /**
     * Send some text to the GATE app, then call reportOutput() to process
     * the results.
     *
     * Note that the following are subclasses of GateException:
     * - ExecutionException
     * - InvalidOffsetException
     * - ResourceInstantiationException
     */

    private void processInput(String text)
            throws ResourceInstantiationException, ExecutionException,
                   IOException, InvalidOffsetException {
        if (m_show_contents_on_crash) {
            m_current_contents_for_crash_debugging = text;
        }
        // Make a document from plain text
        Document doc = Factory.newDocument(text);  // throws ResourceInstantiationException
        // Add the single document to the corpus
        m_corpus.add(doc);

        // Run the application.
        m_log.info("Running application...");
        m_controller.execute();  // throws ExecutionException
        // Simulate GATE crash?
        // throw new ExecutionException("hello");

        m_log.info("Application complete, processing output...");
        reportOutput(doc);
        // remove the document from the corpus again
        m_corpus.clear();
        // Garbage collection
        // https://gate.ac.uk/sale/tao/splitch7.html#chap:api
        Factory.deleteResource(doc);
    }

    // ========================================================================
    // GATE output processing
    // ========================================================================

    /**
     * Does the user wish us to process GATE annotations from a specific
     * annotation set?
     */

    private boolean useSet(String setname) {
        // Check set name against inclusion/exclusion lists.
        // Case-sensitive comparisons used here.
        for (String exclude : m_set_exclusion_list) {
            if (setname.equals(exclude)) {  // .equals(), not ==!
                // Explicitly excluded.
                m_log.debug("Explicitly excluding set: " + toPrintable(setname));
                return false;
            }
        }
        if (m_set_inclusion_list.size() == 0) {
            // Empty inclusion list, which means include everything by default.
            m_log.debug("Including set by default: " + toPrintable(setname));
            return true;
        }
        for (String include : m_set_inclusion_list) {
            if (setname.equals(include)) {  // .equals(), not ==!
                // Explicitly included.
                m_log.debug("Explicitly including set: " + toPrintable(setname));
                return true;
            }
        }
        for (String include : m_set_annotation_combos.keySet()) {
            if (setname.equals(include)) {
                // Explicitly included via a set/annotation pair
                m_log.debug("Including set for set/annotation pair: " +
                            toPrintable(setname));
                return true;
            }
        }
        // An inclusion list has been specified, but our set name isn't on it.
        m_log.debug("Excluding set as not included: " + toPrintable(setname));
        return false;
    }

    /** Which annotation sets does the document provide that the user wants? */

    private Map<String, AnnotationSet> getAnnotationSets(Document doc) {
        // The default of doc.getAnnotations() only gets the default (unnamed)
        // AnnotationSet. But for KConnect/Bio-YODIE, we find an unnamed set,
        // and a set named "Bio", whose annotations look like "Bio#Disease".
        // Similarly, the GATE BRC Pharmacotherapy app has a set named "Output".
        // Sometimes, the default unnamed set provides the same information as
        // a named set, so we need to be able to specify inclusion/exclusion
        // criteria.
        //
        // The underlying functions are:
        //      public AnnotationSet SimpleDocument::getAnnotations();
        //      public AnnotationSet SimpleDocument::getAnnotations(String name);
        // and then the other useful one is:
        //      public Set<String> SimpleDocument::getAnnotationSetNames();

        Map<String, AnnotationSet> sets = new HashMap<String, AnnotationSet>();
        if (useSet("")) {
            sets.put("", doc.getAnnotations());  // the unnamed one
        }
        for (String name : doc.getAnnotationSetNames()) {
            if (useSet(name)) {
                sets.put(name, doc.getAnnotations(name));
            }
        }
        return sets;
    }

    /**
     * For a given set of annotations from a GATE document, find ones of
     * particular types. Process each via processAnnotation(). Also adds them
     * to annotations_to_write, for XML output.
     */

    private void fetchAndProcessAnnotations(
                Document doc,
                PrintStream outtsv,
                String setname,
                AnnotationSet annotations,
                ArrayList<String> target_annots,
                Set<Annotation> annotations_to_write)  // written to; used for XML
            throws InvalidOffsetException, IOException {
        Iterator annot_types_it = target_annots.iterator();
        while (annot_types_it.hasNext()) {
            // Extract all the annotations of each requested type:
            AnnotationSet annots_of_this_type = annotations.get(
                (String)annot_types_it.next());
            if (annots_of_this_type != null) {
                // Add them to the temporary set, for the XML
                annotations_to_write.addAll(annots_of_this_type);
            }
            // Process individual annotations
            Iterator ann_it = annots_of_this_type.iterator();
            while (ann_it.hasNext()) {
                Annotation annot = (Annotation)ann_it.next();
                processAnnotation(setname, annot, doc, outtsv);
            }
        }
    }

    /**
     * Trawl a processed GATE document, find relevant annotations, and write
     * them to our target outputs.
     */

    private void reportOutput(Document doc)
            throws IOException, InvalidOffsetException {
        FeatureMap features = doc.getFeatures();
        String outstring;
        /*
        String original_content = (String)
            features.get(GateConstants.ORIGINAL_DOCUMENT_CONTENT_FEATURE_NAME);
        RepositioningInfo info = (RepositioningInfo)
            features.get(GateConstants.DOCUMENT_REPOSITIONING_INFO_FEATURE_NAME);
        status("original_content: " + original_content);
        status("info: " + info);
        */

        PrintStream outtsv = null;
        if (m_tsv_filename_stem != null) {
            String filename = m_tsv_filename_stem + m_count + ".tsv";
            outtsv = new PrintStream(filename);
        }

        // Fetch relevant output
        if (!m_target_annotations.isEmpty() || !m_set_annotation_combos.isEmpty()) {

            // ----------------------------------------------------------------
            // User has specified annotations to report.
            // ----------------------------------------------------------------

            // Create a temporary Set to hold the annotations we wish to write out
            Set<Annotation> annotations_to_write = new HashSet<Annotation>();

            // Extract the annotations
            Map<String, AnnotationSet> sets = getAnnotationSets(doc);
            for (Map.Entry<String, AnnotationSet> gate_entry : sets.entrySet()) {
                String setname = gate_entry.getKey();
                AnnotationSet annotations = gate_entry.getValue();

                if (!m_target_annotations.isEmpty()) {
                    // Specifying annotations generically
                    fetchAndProcessAnnotations(doc, outtsv, setname,
                                               annotations, m_target_annotations,
                                               annotations_to_write);
                } else {
                    // Specifying set/annotation combinations
                    for (Map.Entry<String, ArrayList<String>> sa_combo_entry :
                            m_set_annotation_combos.entrySet()) {
                        String target_set = sa_combo_entry.getKey();
                        if (!setname.equals(target_set)) {
                            continue;
                        }
                        ArrayList<String> target_annots = sa_combo_entry.getValue();
                        fetchAndProcessAnnotations(doc, outtsv, setname,
                                                   annotations, target_annots,
                                                   annotations_to_write);
                    }
                }
            }

            // Write annotated contents (as XML) to file?
            if (m_annotxml_filename_stem != null) {
                writeXml(m_annotxml_filename_stem,
                         doc.toXml(annotations_to_write));
            }

        } else {

            // ----------------------------------------------------------------
            // No annotations specified. Process them all.
            // ----------------------------------------------------------------

            // Process all of them...
            Map<String, AnnotationSet> sets = getAnnotationSets(doc);
            for (Map.Entry<String, AnnotationSet> entry : sets.entrySet()) {
                String setname = entry.getKey();
                AnnotationSet annotations = entry.getValue();
                Iterator ann_it = annotations.iterator();
                while (ann_it.hasNext()) {
                    Annotation annot = (Annotation)ann_it.next();
                    processAnnotation(setname, annot, doc, outtsv);
                }
            }

            // ... and write the whole thing as GateXML.
            if (m_annotxml_filename_stem != null) {
                writeXml(m_annotxml_filename_stem, doc.toXml());
            }

        }

        if (outtsv != null) {
            outtsv.close();
        }

        // Write GateXML to file?
        if (m_gatexml_filename_stem != null) {
            writeXml(m_gatexml_filename_stem, doc.toXml());
        }

        // Having written to stdout via processAnnotation()...
        writeOutputTerminator();
    }

    /**
     * Write the output terminate to stdout (and clear the "output terminator
     * pending" flag, used by the code that handles GATE crashes).
     */

    private void writeOutputTerminator() {
        println(m_output_terminator);
        // Flushing is not required:
        // http://stackoverflow.com/questions/7166328
        m_output_terminator_pending = false;
    }

    /**
     * Take a GATE annotation, convert it into a key/value output map, and
     * write it to the desired output (e.g. stdout +/- a TSV file).
     */

    private void processAnnotation(String setname, Annotation a, Document doc,
                                   PrintStream outtsv)
            throws InvalidOffsetException, IOException {
        String type = a.getType();
        long id = a.getId();
        long start = a.getStartNode().getOffset().longValue();
        long end = a.getEndNode().getOffset().longValue();
        FeatureMap featuremap = a.getFeatures();
        String content = "" + doc.getContent().getContent(start, end);
        // ... was hard work to discover how to get that into a string!
        // It's a Serializable, I think, not a string. Anyway, this works.

        Map<String, String> outputmap = new HashMap<String, String>();
        outputmap.put(KEY_SET, setname);
        outputmap.put(KEY_TYPE, type);
        outputmap.put(KEY_ID, "" + id);
        // ... http://stackoverflow.com/questions/5071040
        outputmap.put(KEY_STARTPOS, "" + start);
        outputmap.put(KEY_ENDPOS, "" + end);
        outputmap.put(KEY_CONTENT, content);
        for (Map.Entry<Object, Object> entry : featuremap.entrySet()) {
            outputmap.put("" + entry.getKey(), "" + entry.getValue());
        }

        // Primary output
        printMapAsTsvLine(outputmap, m_out);

        // Send to file as well?
        if (outtsv != null) {
            printMapAsTsvLine(outputmap, outtsv);
        }

        // Debugging
        m_log.info("Found annotation of type: " + type);
        m_log.debug(m_sep1 + "ANNOTATION:");
        reportMap(outputmap);
        m_log.debug(m_sep2);
    }

    /** Write a key/value map to an output stream as TSV. */

    private void printMapAsTsvLine(Map<String, String> map,
                                   PrintStream stream) {
        boolean first = true;
        for (Map.Entry<String, String> entry : map.entrySet()) {
            if (!first) {
                stream.print("\t");
            }
            first = false;
            stream.print(entry.getKey());
            stream.print("\t");
            stream.print(escapeTabsNewlines(entry.getValue()));
        }
        stream.print("\n");
    }

    /** Write a key/value map to the debugging log. */

    private void reportMap(Map<String, String> map) {
        for (Map.Entry<String, String> entry : map.entrySet()) {
            m_log.debug(entry.getKey() + ":" +
                        escapeTabsNewlines(entry.getValue()));
        }
    }

    // ========================================================================
    // Main (run from the command line)
    // ========================================================================

    /** main(); create and run our pipeline. */

    public static void main(String args[]) throws GateException, IOException {
        CrateGatePipeline pipeline = new CrateGatePipeline(args);
    }

}
