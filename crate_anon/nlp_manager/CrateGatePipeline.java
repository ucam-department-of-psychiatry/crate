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
    // Text
    private static final String m_sep1 = ">>>>>>>>>>>>>>>>> ";
    private static final String m_sep2 = "<<<<<<<<<<<<<<<<<";
    // Internal
    private String m_extra_log_prefix = "";
    private int m_count = 0;
    private String m_pipe_encoding = "UTF-8";
    private PrintStream m_out = null;
    private String m_current_contents_for_crash_debugging = null;
    // Logger:
    private static final Logger m_log = Logger.getLogger(CrateGatePipeline.class);

    // GATE things
    private CorpusController m_controller = null;
    private Corpus m_corpus = null;

    // ========================================================================
    // Constructor
    // ========================================================================

    public CrateGatePipeline(String args[])
            throws GateException, IOException, ResourceInstantiationException {
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

        // --------------------------------------------------------------------
        // Do interesting things
        // --------------------------------------------------------------------
        reportArgs(true);
        try {
            runPipeline();
        } catch (Exception e) {
            m_log.error("Uncaught exception; aborting; stack trace follows");
            e.printStackTrace(); // *** CHECK: ALWAYS GOING TO STDERR?
            if (m_show_contents_on_crash) {
                if (m_current_contents_for_crash_debugging == null) {
                    m_log.error("No current contents");
                } else {
                    m_log.error("Current contents being processed:");
                    writeStderr(m_current_contents_for_crash_debugging);
                }
            }
            abort();  // otherwise, Java exits with an UNDEFINED (e.g. 0 = "happy") return code
        }
    }

    private void runPipeline()
            throws GateException, IOException, ResourceInstantiationException {
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

            // Process text
            processInput(result.contents);

            ++m_count;
        } while (!result.finished);
    }

    // ========================================================================
    // Handling of args, exiting, etc.
    // ========================================================================

    private void exit() {
        System.exit(0);
    }

    private void abort() {
        System.exit(1);
    }

    private void argfail(String msg) {
        // Don't use the log; it's not configured yet.
        writeStderr(msg);
        reportArgs(false);
        abort();
    }

    private void usage() {
        writeStderr(
"usage: CrateGatePipeline -g GATEAPP [-a ANN [-a ANN [...]]] [-e ENCODING]\n" +
"                         [-h] [-it TERM] [-ot TERM] [-v [-v]]\n" +
"                         [-wa FILESTEM] [-wg FILESTEM] [-wt FILESTEM]\n" +
"\n" +
"Java front end to GATE natural language processor.\n" +
"Takes input on stdin. Produces output on stdout.\n" +
"\n" +
"required arguments:\n" +
"  -g GATEAPP       Specifies the GATE app (.gapp/.xgapp) file to use.\n" +
"\n" +
"optional arguments:\n" +
"  -a ANNOT         Adds the specified annotation to the target list.\n" +
"  -e ENCODING      The character encoding of the source documents, to be used\n" +
"                   for file output. If not specified, the platform default\n" +
"                   encoding (currently \"" + System.getProperty("file.encoding") + "\") is assumed.\n" +
"  -h               Show this help message and exit.\n" +
"  -it TERMINATOR   Specify stdin end-of-document terminator.\n" +
"  -ot TERMINATOR   Specify stdout end-of-document terminator.\n" +
"  -lt LOGTAG       Use an additional tag for stderr logging.\n" +
"                   Helpful in multiprocess environments.\n" +
"  -v               Verbose (use up to 3 times to be more verbose).\n" +
"  -wa FILESTEM     Write annotated XML document to FILESTEM<n>.xml, where <n>\n" +
"                   is the file's sequence number (starting from 0).\n" +
"  -wg FILESTEM     Write GateXML document to FILESTEM<n>.xml.\n" +
"  -wt FILESTEM     Write TSV-format annotations FILESTEM<n>.tsv.\n" +
"  -s               Suppress any stdout from GATE application.\n" +
"  -show_contents_on_crash\n" +
"                   If GATE crashes, report the current text to stderr.\n" +
"                   (WARNING: likely to contain identifiable material.)\n"
        );
    }

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
                case "-a":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_target_annotations.add(m_args[i++]);
                    break;
                case "-e":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_file_encoding = m_args[i++];
                    break;
                case "-g":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_gapp_file = new File(m_args[i++]);
                    break;
                case "-h":
                    usage();
                    exit();
                    break;
                case "-it":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_input_terminator = m_args[i++];
                    break;
                case "-ot":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_output_terminator = m_args[i++];
                    break;
                case "-lt":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_extra_log_prefix = m_args[i++];
                    break;
                case "-v":
                    m_verbose++;
                    break;
                case "-wa":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_annotxml_filename_stem = m_args[i++];
                    break;
                case "-wg":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_gatexml_filename_stem = m_args[i++];
                    break;
                case "-wt":
                    if (nleft < 1) argfail(insufficient + arg);
                    m_tsv_filename_stem = m_args[i++];
                    break;
                case "-s":
                    m_suppress_gate_stdout = true;
                    break;
                case "-show_contents_on_crash":
                    m_show_contents_on_crash = true;
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
    }

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

    private String escapePercent(String s) {
        if (s == null) {
            return s;
        }
        s = s.replace("%", "%%");
        return s;
    }

    // ========================================================================
    // stdin handling
    // ========================================================================

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

    private StdinResult readStdin() throws IOException {
        BufferedReader br = new BufferedReader(
            new InputStreamReader(System.in, m_pipe_encoding));
        StringBuffer sb = new StringBuffer();
        String line;
        boolean finished_this = false;
        boolean finished_everything = false;
        while (!finished_this) {
            line = br.readLine();
            if (line == null) {
                finished_this = true;
                finished_everything = true;
            } else if (line.equals(m_input_terminator)) {
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

    private void writeStderr(String msg) {
        System.err.println(msg);
    }

    private void print(String msg) {
        m_out.print(msg);
    }

    private void println(String msg) {
        m_out.println(msg);
    }

    // ========================================================================
    // File handling
    // ========================================================================

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

    private void writeXml(String stem, String xml)
            throws FileNotFoundException, UnsupportedEncodingException,
            IOException {
        String filename = stem + m_count + ".xml";
        writeToFile(filename, xml);
    }

    // ========================================================================
    // GATE input processing
    // ========================================================================

    private void setupGate()
            throws GateException, IOException, ResourceInstantiationException {
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
        m_corpus = Factory.newCorpus("CrateGatePipeline corpus");
        // Tell the controller about the corpus
        m_controller.setCorpus(m_corpus);
        m_log.info("... corpus initialized");
    }

    private void processInput(String text)
            throws ResourceInstantiationException, ExecutionException,
                   IOException, InvalidOffsetException {
        // Make a document from plain text
        Document doc = Factory.newDocument(text);
        // Add the single document to the corpus
        m_corpus.add(doc);
        // Run the application.
        m_log.info("Running application...");
        m_controller.execute();
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

    private Map<String, AnnotationSet> getAnnotationSets(Document doc) {
        // The default of doc.getAnnotations() only gets the default (unnamed)
        // AnnotationSet. But for KConnect/Bio-YODIE, we find an unnamed set,
        // and a set named "Bio", whose annotations look like "Bio#Disease".
        //
        // The underlying functions are:
        //      public AnnotationSet SimpleDocument::getAnnotations();
        //      public AnnotationSet SimpleDocument::getAnnotations(String name);
        // and then the other useful one is:
        //      public Set<String> SimpleDocument::getAnnotationSetNames();

        Map<String, AnnotationSet> sets = new HashMap<String, AnnotationSet>();
        sets.put("", doc.getAnnotations());  // the unnamed one
        for (String name : doc.getAnnotationSetNames()) {
            sets.put(name, doc.getAnnotations(name));
        }
        return sets;
    }

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
        if (!m_target_annotations.isEmpty()) {

            // ----------------------------------------------------------------
            // User has specified annotations to report.
            // ----------------------------------------------------------------

            // Create a temporary Set to hold the annotations we wish to write out
            Set<Annotation> annotations_to_write = new HashSet<Annotation>();

            // Extract the annotations
            Map<String, AnnotationSet> sets = getAnnotationSets(doc);
            for (Map.Entry<String, AnnotationSet> entry : sets.entrySet()) {
                String name = entry.getKey();
                AnnotationSet annotations = entry.getValue();
                Iterator annot_types_it = m_target_annotations.iterator();
                while (annot_types_it.hasNext()) {
                    // extract all the annotations of each requested type and
                    // add them to the temporary set
                    AnnotationSet annots_of_this_type = annotations.get(
                        (String)annot_types_it.next());
                    if (annots_of_this_type != null) {
                        annotations_to_write.addAll(annots_of_this_type);
                    }
                }
            }

            // Process individual annotations
            Iterator ann_it = annotations_to_write.iterator();
            while (ann_it.hasNext()) {
                Annotation annot = (Annotation)ann_it.next();
                processAnnotation(annot, doc, outtsv);
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
                String name = entry.getKey();
                AnnotationSet annotations = entry.getValue();
                Iterator ann_it = annotations.iterator();
                while (ann_it.hasNext()) {
                    Annotation annot = (Annotation)ann_it.next();
                    processAnnotation(annot, doc, outtsv);
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
        println(m_output_terminator);
        // Flushing is not required:
        // http://stackoverflow.com/questions/7166328
    }

    private void processAnnotation(Annotation a, Document doc,
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
        outputmap.put("_type", type);
        outputmap.put("_id", "" + id);
        // ... http://stackoverflow.com/questions/5071040
        outputmap.put("_start", "" + start);
        outputmap.put("_end", "" + end);
        outputmap.put("_content", content);
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

    private void reportMap(Map<String, String> map) {
        for (Map.Entry<String, String> entry : map.entrySet()) {
            m_log.debug(entry.getKey() + ":" +
                        escapeTabsNewlines(entry.getValue()));
        }
    }

    // ========================================================================
    // Main (run from the command line)
    // ========================================================================

    public static void main(String args[]) throws GateException, IOException {
        CrateGatePipeline pipeline = new CrateGatePipeline(args);
    }
}
