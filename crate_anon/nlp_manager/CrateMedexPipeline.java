/*

CrateMedexPipeline.java

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
    private String m_file_encoding = null;  // null: use system default
    private int m_verbose = 0;
    // Internal
    private String m_logprefix = m_defaultlogprefix;
    private int m_count = 0;
    private String m_std_encoding = "UTF-8";
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
	private String m_if_freq_norm = "n";  // -f [yn]: normalize frequency to TIMEX3 format? (e.g. "b.i.d." -> "R1P12H")
	private String m_if_drool_engine = "n";  // -d [yn]: "use drool engine? ... The default setting is to use the built-in rules for disambiguation (faster)"
	private String m_if_offset_showed = "y";  // -p [yn]: show offset information?
	private String m_if_output_tag = "n";  // -t [yn]: show tagging information?
    private String m_input_dir = null;
    private String m_output_dir = null;

    // ========================================================================
    // Constructor
    // ========================================================================

    public CrateMedexPipeline(String args[]) throws IOException {
        m_stdout = new PrintStream(System.out, true, m_std_encoding);
        m_args = args;
        process_args();
        if (m_verbose > 0) {
            report_args();
        }

        setup_medex();
        status("Ready for input");

        // Wait for each "data ready" signal, then process files.
        BufferedReader br = new BufferedReader(
            new InputStreamReader(System.in, m_std_encoding));
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
                process_input();
                signal_results_ready();
                ++m_count;
            }
        }
    }

    // ========================================================================
    // Handling of args, stdin, etc.
    // ========================================================================

    private void exit() {
        System.exit(0);
    }

    private void abort() {
        System.exit(1);
    }

    private void fail(String msg) {
        status(msg);
        abort();
    }

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

    private void process_args() {
        int i = 0;
        int nleft;
        String arg;
        String insufficient = "insufficient arguments";
        // Process
        while (i < m_args.length) {
            arg = m_args[i++].toLowerCase();
            nleft = m_args.length - i;
            switch (arg) {
                case "-i":
                    if (nleft < 1) fail(insufficient);
                    m_input_dir = m_args[i++];
                    break;
                case "-o":
                    if (nleft < 1) fail(insufficient);
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
                    if (nleft < 1) fail(insufficient);
                    set_logtag(m_args[i++]);
                    break;
                case "-data_ready_signal":
                    if (nleft < 1) fail(insufficient);
                    m_data_ready_signal = m_args[i++];
                    break;
                case "-results_ready_signal":
                    if (nleft < 1) fail(insufficient);
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
            status("missing -inputdir parameter; use -h for help");
            abort();
        }
        if (m_output_dir == null) {
            status("missing -outputdir parameter; use -h for help");
            abort();
        }
    }

    private void report_args() {
        for (int i = 0; i < m_args.length; i++) {
            status("Arg " + i + " = " + m_args[i]);
        }
    }

    private void set_logtag(String msg) {
        m_logprefix = m_defaultlogprefix;
        if (m_logprefix.length() > 0) {
            m_logprefix += msg + ":";
        }
    }

    private String now() {
        return m_datetimefmt.format(Calendar.getInstance().getTime());
    }

    private void status(String msg) {
        status(msg, true);
    }

    private void status(String msg, boolean prefix) {
        System.err.println((prefix ? (now() + ":" + m_logprefix) : "") + msg);
    }

    private void print(String msg) {
        m_stdout.print(msg);
    }

    private void println(String msg) {
        // status("println: " + msg);
        m_stdout.println(msg);
    }

    // ========================================================================
    // MedEx input processing
    // ========================================================================

    private String resource(String stem) {
        return m_location + ".." + File.separator + "resources" + File.separator + stem;
    }

    private void setup_medex() throws IOException {
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

    private void process_input() throws IOException {
        m_medtagger.run_batch_medtag();
    }

    // ========================================================================
    // MedEx output processing
    // ========================================================================

    private void signal_results_ready() throws IOException {
        println(m_results_ready_signal);
        // Flushing is not required:
        // http://stackoverflow.com/questions/7166328
    }

    // ========================================================================
    // Main (run from the command line)
    // ========================================================================

    public static void main(String args[]) throws IOException {
        CrateMedexPipeline medex = new CrateMedexPipeline(args);
    }
}
