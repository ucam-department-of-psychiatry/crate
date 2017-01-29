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

import gate.*;
import gate.creole.*;
import gate.util.*;
import gate.util.persistence.PersistenceManager;
import gate.corpora.RepositioningInfo;

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
    private ArrayList<String> m_target_annotations = null;
    private String m_input_terminator = m_default_input_terminator;
    private String m_output_terminator = m_default_output_terminator;
    private File m_gapp_file = null;
    private String m_file_encoding = null;  // null: use system default
    private int m_verbose = 0;
    private String m_annotxml_filename_stem = null;
    private String m_gatexml_filename_stem = null;
    private String m_tsv_filename_stem = null;
    // Text
    private static final String m_sep1 = ">>>>>>>>>>>>>>>>> ";
    private static final String m_sep2 = "<<<<<<<<<<<<<<<<<";
    // Internal
    private String m_extra_log_prefix = "";
    private int m_count = 0;
    private String m_std_encoding = "UTF-8";
    private PrintStream m_out = null;
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
        Level main_level = m_verbose >= 2 ? Level.DEBUG
                                          : (m_verbose >= 1 ? Level.INFO
                                                            : Level.WARN);
        Level gate_level = m_verbose >= 3 ? Level.DEBUG
                                          : (m_verbose >= 1 ? Level.INFO
                                                            : Level.WARN);
        configureLog(m_log, main_level, m_extra_log_prefix);
        configureLog(Logger.getLogger("gate"), gate_level, "");

        // --------------------------------------------------------------------
        // Setup stdout
        // --------------------------------------------------------------------
        m_out = new PrintStream(System.out, true, m_std_encoding);

        // --------------------------------------------------------------------
        // Do interesting things
        // --------------------------------------------------------------------
        reportArgs();
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
            m_log.info("Read text");
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
"  -wt FILESTEM     Write TSV-format annotations FILESTEM<n>.tsv.\n"
        );
    }

    private void processArgs() {
        int i = 0;
        int nleft;
        String arg;
        String insufficient = "Insufficient arguments";
        // Process
        while (i < m_args.length) {
            arg = m_args[i++].toLowerCase();
            nleft = m_args.length - i;
            switch (arg) {
                case "-a":
                    if (nleft < 1) argfail(insufficient);
                    if (m_target_annotations == null) {
                        m_target_annotations = new ArrayList<String>();
                    }
                    m_target_annotations.add(m_args[i++]);
                    break;
                case "-e":
                    if (nleft < 1) argfail(insufficient);
                    m_file_encoding = m_args[i++];
                    break;
                case "-g":
                    if (nleft < 1) argfail(insufficient);
                    m_gapp_file = new File(m_args[i++]);
                    break;
                case "-h":
                    usage();
                    exit();
                    break;
                case "-it":
                    if (nleft < 1) argfail(insufficient);
                    m_input_terminator = m_args[i++];
                    break;
                case "-ot":
                    if (nleft < 1) argfail(insufficient);
                    m_output_terminator = m_args[i++];
                    break;
                case "-lt":
                    if (nleft < 1) argfail(insufficient);
                    m_extra_log_prefix = m_args[i++];
                    break;
                case "-v":
                    m_verbose++;
                    break;
                case "-wa":
                    if (nleft < 1) argfail(insufficient);
                    m_annotxml_filename_stem = m_args[i++];
                    break;
                case "-wg":
                    if (nleft < 1) argfail(insufficient);
                    m_gatexml_filename_stem = m_args[i++];
                    break;
                case "-wt":
                    if (nleft < 1) argfail(insufficient);
                    m_tsv_filename_stem = m_args[i++];
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

    private void reportArgs() {
        for (int i = 0; i < m_args.length; i++) {
            m_log.debug("Arg " + i + " = " + m_args[i]);
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
            new InputStreamReader(System.in, m_std_encoding));
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

    private void configureLog(Logger log, Level level, String logtag) {
        // http://stackoverflow.com/questions/8965946/configuring-log4j-loggers-programmatically
        // https://logging.apache.org/log4j/1.2/apidocs/org/apache/log4j/PatternLayout.html
        String tag = "";
        if (!logtag.isEmpty()) {
            tag += "|" + escapePercent(logtag);
        }
        String log_pattern = "%d{yyyy-MM-dd HH:mm:ss.SSS} [%p|%c" + tag + "] %m%n";
        PatternLayout log_layout = new PatternLayout(log_pattern);
        ConsoleAppender log_appender = new ConsoleAppender(log_layout, "System.err");
        log.addAppender(log_appender);
        log.setLevel(level);
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

    private void reportOutput(Document doc)
            throws IOException, InvalidOffsetException {
        FeatureMap features = doc.getFeatures();
        String outstring;
        /*
        String originalContent = (String)
            features.get(GateConstants.ORIGINAL_DOCUMENT_CONTENT_FEATURE_NAME);
        RepositioningInfo info = (RepositioningInfo)
            features.get(GateConstants.DOCUMENT_REPOSITIONING_INFO_FEATURE_NAME);
        status("originalContent: " + originalContent);
        status("info: " + info);
        */

        PrintStream outtsv = null;
        if (m_tsv_filename_stem != null) {
            String filename = m_tsv_filename_stem + m_count + ".tsv";
            outtsv = new PrintStream(filename);
        }

        // Fetch relevant output
        if (m_target_annotations != null) {
            // User has specified annotations to report.
            // Create a temporary Set to hold the annotations we wish to write out
            Set<Annotation> annotationsToWrite = new HashSet<Annotation>();
            // We only extract annotations from the default (unnamed)
            // AnnotationSet in this example
            AnnotationSet defaultAnnots = doc.getAnnotations();
            Iterator annotTypesIt = m_target_annotations.iterator();
            while (annotTypesIt.hasNext()) {
                // extract all the annotations of each requested type and add
                // them to the temporary set
                AnnotationSet annotsOfThisType = defaultAnnots.get(
                    (String)annotTypesIt.next());
                if (annotsOfThisType != null) {
                    annotationsToWrite.addAll(annotsOfThisType);
                }
            }
            // Process individual annotations
            Iterator annIt = annotationsToWrite.iterator();
            while (annIt.hasNext()) {
                Annotation annot = (Annotation)annIt.next();
                processAnnotation(annot, doc, outtsv);
            }
            // Write annotated contents (as XML) to file?
            if (m_annotxml_filename_stem != null) {
                writeXml(m_annotxml_filename_stem,
                         doc.toXml(annotationsToWrite));
            }
        } else {
            // No annotations specified.
            // Process all of them and write the whole thing as GateXML.
            AnnotationSet annotations = doc.getAnnotations();
            Iterator annIt = annotations.iterator();
            while (annIt.hasNext()) {
                Annotation annot = (Annotation)annIt.next();
                processAnnotation(annot, doc, outtsv);
            }
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
