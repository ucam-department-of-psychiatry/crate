/*

CrateMedexPipeline.java

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

Implements a Java interface to MedEx-UIMA that receives "data is available"
signals and returns "processed data ready for collection" signals via
stdin/stdout. See medex_parser.py.

Note in particular:

- the MedTagger class opens "sents/X" (where X is the input file) from the
  directory System.getProperty("user.dir"), curse it.

  - That is the directory from which you run the Java program.

  - It's hard to set the "user.dir" property reliably, apparently:
    http://stackoverflow.com/questions/840190/changing-the-current-working-directory-in-java
    ... I comment in passing that this is not something that makes one think
    "Java - wow"...

  - So we must simply CALL THIS PROGRAM FROM AN APPROPRIATE (e.g. temporary)
    DIRECTORY, AND MAKE DIRECTORIES IT WANTS:

        sents
        log

*/

// no "package" command required

import java.util.*;
import java.io.*;
import java.text.SimpleDateFormat;

import org.apache.medex.MedTagger;

/**
 * CrateMedexPipeline is a command-line program that fires up MedEx, reads
 * "data ready" signals from stdin, asks MedEx to process input disk files into
 * output disk files, and writes "results ready" signals to stdout.
 */

public class CrateMedexPipeline {

    // ========================================================================
    // Members
    // ========================================================================

    // Constants
    private static final String m_defaultlogprefix = "crate_medex_pipeline:";
    private static final String m_default_data_ready_signal = "DATA_READY";
    private static final String m_default_results_ready_signal = "RESULTS_READY";
    private static final SimpleDateFormat m_datetimefmt = new SimpleDateFormat(
        "yyyy-MM-dd HH:mm:ss.SSS");
    private static final String TAB = "\t";
    private static final String NEWLINE = "\n";
    // Interface
    private String m_args[];
    // Options
    private String m_data_ready_signal = m_default_data_ready_signal;
    private String m_results_ready_signal = m_default_results_ready_signal;
    // UNUSED // private String m_file_encoding = "UTF-8";  // null would be: use system default
    private int m_verbose = 0;
    // Internal
    private String m_logprefix = m_defaultlogprefix;
    private int m_count = 0;
    private String m_pipe_encoding = "UTF-8";
    private PrintStream m_stdout = null;
    // MedEx tagger object
    private MedTagger m_medtagger = null;
    // MedEx options
    // ... this ugly file-finding code is as per MedEx:
	private static String m_location = MedTagger.class.getProtectionDomain().getCodeSource().getLocation().getPath();
	private String m_lexicon_file = resource("lexicon.cfg");
	private String m_rxnorm_file = resource("brand_generic.cfg");
	private String m_code_file = resource("code.cfg");
	private String m_generic_file = resource("rxcui_generic.cfg");
	private String m_norm_file = resource("norm.cfg");
	private String m_word_file = resource("word.txt");
	private String m_abbr_file = resource("abbr.txt");
	private String m_grammar_file = resource("grammar.txt");
	private String m_if_detect_sents = "y";  // -b [yn]: use built-in sentence boundary detector?
	private String m_if_freq_norm = "y";  // -f [yn]: normalize frequency to TIMEX3 format? (e.g. "b.i.d." -> "R1P12H")
	private String m_if_drool_engine = "n";  // -d [yn]: "use drool engine? ... The default setting is to use the built-in rules for disambiguation (faster)"
	private String m_if_offset_showed = "y";  // -p [yn]: show offset information?
	private String m_if_output_tag = "n";  // -t [yn]: show tagging information?
    private String m_input_dir = null;
    private String m_output_dir = null;

    // ========================================================================
    // Constructor
    // ========================================================================

    /** Process command-line arguments and execute the pipeline. */

    public CrateMedexPipeline(String args[]) throws IOException {
        m_stdout = new PrintStream(System.out, true, m_pipe_encoding);
        m_args = args;
        processArgs();
        if (m_verbose > 0) {
            reportArgs();
        }

        try {
            runPipeline();
        } catch (Exception e) {
            status("Uncaught exception; aborting; stack trace follows");
            e.printStackTrace();
            abort();  // otherwise, Java exits with an UNDEFINED (e.g. 0 = "happy") return code

            // NOTE ALSO THAT MEDEX CATCHES ITS OWN GENERAL EXCEPTIONS, PRINTS
            // A STACK TRACE, AND CARRIES ON. See e.g. MedTagger.java, and
            // search for printStackTrace.
        }
    }

    /**
     * Starts MedEx; read "data ready" signals from stdin; asks MedEx to
     * batch-process files on disk (creating output disk files); writes
     * "results ready" signals to stdout.
     */

    private void runPipeline() throws IOException {
        setupMedex();
        status("Ready for input");

        // Wait for each "data ready" signal, then process files.
        BufferedReader br = new BufferedReader(
            new InputStreamReader(System.in, m_pipe_encoding));
        String line;
        boolean finished = false;
        while (!finished) {
            line = br.readLine();
            if (m_verbose >= 2) {
                status("Contents of stdin: " + line);
            }
            if (line == null) {
                finished = true;
            } else if (line.equals(m_data_ready_signal)) {
                // Process text
                processInput();
                signalResultsReady();
                ++m_count;
            }
        }
    }

    // ========================================================================
    // Handling of args, stdin, etc.
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

    private void fail(String msg) {
        status(msg);
        reportArgs();
        abort();
    }

    /** Show a usage message. */

    private void usage() {
        status(
"usage: CrateMedexPipeline -i DIR -o DIR\n" +
"                          [-h] [-v [-v]] [-lt LOGTAG]\n" +
"                          [-data_ready_signal DATA_READY]\n" +
"                          [-results_ready_signal RESULTS_READY]\n" +
"\n" +
"Java front end to MedEx-UIMA natural language processor for drugs.\n" +
"Takes signals on stdin, and data on disk.\n" +
"Writes signals to stdout, and data to disk.\n" +
"\n" +
"required arguments:\n" +
"  -i DIR           (*) Specifies the input directory to read text from.\n" +
"  -o DIR           (*) Specifies the input directory to write results to.\n" +
"\n" +
"optional arguments:\n" +
"  -h               Show this help message and exit.\n" +
"  -v               Verbose (use twice to be more verbose).\n" +
"  -lt LOGTAG       Use an additional tag for stderr logging.\n" +
"                   Helpful in multiprocess environments.\n" +
"  -data_ready_signal DATA_READY\n" +
"                   Sets the 'data ready' signal that this program waits for\n" +
"                   on stdin before scanning for data.\n" +
"  -results_ready_signal RESULTS_READY\n" +
"                   Sets the 'data ready' signal that this program sends on\n" +
"                   stdout once results are ready on disk.\n" +
"\n" +
"(*) MedEx argument\n",
            false
        );
    }

    /**
     * Process command-line arguments from m_args, and set internal variables.
     */

    private void processArgs() {
        int i = 0;
        int nleft;
        String arg;
        String insufficient = "CrateMedexPipeline: Insufficient arguments while processing ";
        // Process
        while (i < m_args.length) {
            arg = m_args[i++].toLowerCase();
            nleft = m_args.length - i;
            switch (arg) {
                case "-i":
                    if (nleft < 1) fail(insufficient + arg);
                    m_input_dir = m_args[i++];
                    break;
                case "-o":
                    if (nleft < 1) fail(insufficient + arg);
                    m_output_dir = m_args[i++];
                    break;
                case "-h":
                    usage();
                    exit();
                    break;
                case "-v":
                    m_verbose++;
                    break;
                case "-lt":
                    if (nleft < 1) fail(insufficient + arg);
                    setLogTag(m_args[i++]);
                    break;
                case "-data_ready_signal":
                    if (nleft < 1) fail(insufficient + arg);
                    m_data_ready_signal = m_args[i++];
                    break;
                case "-results_ready_signal":
                    if (nleft < 1) fail(insufficient + arg);
                    m_results_ready_signal = m_args[i++];
                    break;
                default:
                    usage();
                    abort();
                    break;
            }
        }
        // Validate
        if (m_input_dir == null) {
            status("missing -i parameter; use -h for help");
            abort();
        }
        if (m_output_dir == null) {
            status("missing -o parameter; use -h for help");
            abort();
        }
    }

    /** Report command-line arguments (from m_args). */

    private void reportArgs() {
        for (int i = 0; i < m_args.length; i++) {
            status("Arg " + i + " = " + m_args[i]);
        }
    }

    /**
     * Set the log tag (providing extra information relating to who called us.
     */

    private void setLogTag(String msg) {
        m_logprefix = m_defaultlogprefix;
        if (m_logprefix.length() > 0) {
            m_logprefix += msg + ":";
        }
    }

    /** Returns the current date/time, for log output. */

    private String now() {
        return m_datetimefmt.format(Calendar.getInstance().getTime());
    }

    /** Write a (prefixed) status message to the log. */

    private void status(String msg) {
        status(msg, true);
    }

    /** Write a message to the log, optionally with a date/time/logtag prefix. */

    private void status(String msg, boolean prefix) {
        System.err.println((prefix ? (now() + ":" + m_logprefix) : "") + msg);
    }

    /** Prints a string to stdout. */

    private void print(String msg) {
        m_stdout.print(msg);
    }

    /** Prints a string to stdout and line-terminates it. */

    private void println(String msg) {
        // status("println: " + msg);
        m_stdout.println(msg);
    }

    // ========================================================================
    // MedEx input processing
    // ========================================================================

    /** Returns the filename of a MedEx resource file. */

    private String resource(String stem) {
        return m_location + ".." + File.separator + "resources" + File.separator + stem;
    }

    /** Creates a MedEx processor (tagger). */

    private void setupMedex() throws IOException {
        status("Starting MedEx...");
        m_medtagger = new MedTagger(m_lexicon_file,
                                    m_rxnorm_file,
                                    m_code_file,
                                    m_generic_file,
                                    m_input_dir,
                                    m_output_dir,
                                    m_word_file,
                                    m_abbr_file,
                                    m_grammar_file,
                                    m_if_detect_sents,
                                    m_norm_file,
                                    m_if_freq_norm,
                                    m_if_drool_engine,
                                    m_if_offset_showed,
                                    m_if_output_tag);
        status("... done");
    }

    /**
     * Asks MedEx to batch-process files in our input directory and write
     * results to our output directory.
     */

    private void processInput() throws IOException {
        m_medtagger.run_batch_medtag();
    }

    // ========================================================================
    // MedEx output processing
    // ========================================================================

    /** Indicate on stdout that results are ready in our output files. */

    private void signalResultsReady() throws IOException {
        println(m_results_ready_signal);
        // Flushing is not required:
        // http://stackoverflow.com/questions/7166328
    }

    // ========================================================================
    // Main (run from the command line)
    // ========================================================================

    /** main(); create and run our pipeline. */

    public static void main(String args[]) throws IOException {
        CrateMedexPipeline medex = new CrateMedexPipeline(args);
    }
}
