#!/usr/bin/env python

"""
crate_anon/anonymise/eponyms.py

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

**Medical eponym handling.**

Eponyms from 2018-03-27 snapshot of:

- https://en.wikipedia.org/wiki/List_of_eponymously_named_diseases

Remember the following:

- Patient names should be removed using their identifiable information.
  Removing all known names is just an additional experimental safety measure.
- The eponyms are removed from the name lists, before the name lists are
  used to scrub text -- so we don't scrub "Parkinson's disease", as an
  obvious example.
- Consequently, we can be quite liberal here. Including "Turner", for example
  (a common UK name but also in Turner's syndrome) won't prevent a Mr Turner
  from being anonymised.
- However, the point is to scrub out some inadvertent names, so maybe not
  too liberal!

"""

from typing import Dict, List, Optional

from unidecode import unidecode


class EponymInfo(object):
    """
    Reserved for future use, the intention being maybe some classification by
    how rare or common (a) the eponymous disease is, and (b) the name itself
    is.
    """
    pass


EPONYM_DICT = {}  # type: Dict[str, Optional[EponymInfo]]


def get_plain_eponyms(add_unaccented_versions: bool = True) -> List[str]:
    """
    Returns a list of all names to be used as medical eponyms -- that is,
    people who've had syndromes named after them.

    Args:
        add_unaccented_versions:
            Add unaccented (mangled) versions of names, too? For example, do
            you want Sjogren as well as Sjögren?

    Returns:
        alphabetically sorted list of strings

    """
    eponyms = list(EPONYM_DICT.keys())
    if add_unaccented_versions:
        ep_set = set(eponyms)
        for proper in eponyms:
            deaccented = unidecode(proper)
            ep_set.add(deaccented)
        return sorted(ep_set)
    else:
        return sorted(eponyms)


def _add_eponym(composite: str,
                sep: str = "–",
                info: EponymInfo = None) -> None:
    """
    Adds an eponym to the global eponym dictionary.
    If a composite eponym is supplied, adds each part of it.

    Args:
        composite:
            an eponym like ``"Parkinson"``, or a composite eponym like
            ``"Beckwith–Wiedemann"``
        sep:
            the string that separates parts of a composite eponym
        info:
            optional :class:`EponymInfo` instance; reserved for future
            functionality
    """
    global EPONYM_DICT
    for name in composite.split(sep):
        if name not in EPONYM_DICT:
            EPONYM_DICT[name] = info


# noinspection PyPep8
SIMPLE_EPONYM_LIST = [
    # -------------------------------------------------------------------------
    # A
    # -------------------------------------------------------------------------
    # Aarskog–Scott syndrome (a.k.a. Aarskog syndrome) – Dagfinn Aarskog, Charles I. Scott, Jr.
    "Aarskog–Scott",
    # Aase–Smith syndrome (a.k.a. Aase syndrome) – Jon Morton Aase, David Weyhe Smith
    "Aase–Smith",
    # Abdallat–Davis–Farrage syndrome – Adnan Al Abdallat, S.M. Davis, James Robert Farrage
    "Abdallat–Davis–Farrage",
    # Abderhalden–Kaufmann–Lignac syndrome (a.k.a. Abderhalden–Lignac–Kaufmann disease) – Emil Abderhalden, Eduard Kauffman, George Lignac
    "Abderhalden–Kaufmann–Lignac",
    # Abercrombie disease (a.k.a. Abercrombie syndrome) – John Abercrombie
    "Abercrombie",
    # Achard–Thiers syndrome – Emile Achard, Joseph Thiers
    "Achard–Thiers",
    # Ackerman tumor – Lauren Ackerman
    "Ackerman",
    # Adams–Oliver syndrome – Robert Adams, William Oliver
    "Adams–Oliver",
    # Adams–Stokes syndrome (a.k.a. Gerbec–Morgagni–Adams–Stokes syndrome, Gerbezius–Morgagni–Adams–Stokes syndrome, Stokes–Adams syndrome) – Robert Adams, William Stokes
    "Adams–Stokes",
    # Addison disease – Thomas Addison
    "Addison",
    # Adson–Caffey syndrome – Alfred Washington Adson, I. R. Caffey
    "Adson–Caffey",
    # Ahumada–Del Castillo syndrome – Juan Carlos Ahumada Sotomayor, Enrique Benjamin Del Castillo
    "Ahumada–Del Castillo",
    # Aicardi syndrome – Jean Aicardi
    "Aicardi",
    # Aicardi–Goutières syndrome – Jean Aicardi, Francoise Goutieres
    "Aicardi–Goutières",
    # Alagille syndrome – Daniel Alagille
    "Alagille",
    # Albers-Schönberg disease – Heinrich Albers-Schönberg
    "Albers-Schönberg",
    # Albright disease (a.k.a. Albright hereditary osteodystrophy, Albright syndrome, McCune–Albight syndrome) – Fuller Albright
    "Albright",
    # Albright–Butler–Bloomberg disease – Fuller Albright, Allan Macy Butler, Esther Bloomberg
    "Albright–Butler–Bloomberg",
    # Albright–Hadorn syndrome – Fuller Albright, Walter Hadorn
    "Albright–Hadorn",
    # Albright IV syndrome (a.k.a. Martin–Albright syndrome) – Fuller Albright
    "Albright",
    # Alexander disease – William Stuart Alexander
    "Alexander",
    # Alibert–Bazin syndrome – Jean-Louis-Marc Alibert, Pierre-Antoine-Ernest Bazin
    "Alibert–Bazin",
    # Alpers–Huttenlocher syndrome (a.k.a. Alpers disease, Alpers syndrome) – Bernard Jacob Alpers, Peter Huttenlocher
    "Alpers–Huttenlocher",
    # Alport syndrome – Arthur Cecil Alport
    "Alport",
    # Alström syndrome – Carl Henry Alström
    "Alström",
    # Alvarez' syndrome – Walter C. Alvarez
    "Alvarez",
    # Alzheimer disease – Alois Alzheimer
    "Alzheimer",
    # Anders disease – James Meschter Anders
    "Anders",
    # Andersen disease – Dorothy Andersen
    "Andersen",
    # Andersen–Tawil syndrome (a.k.a. Andersen syndrome) – Ellen Andersen, Al-Rabi Tawil
    "Andersen–Tawil",
    # Anderson–Fabry disease – William Anderson, Johannes Fabry
    "Anderson–Fabry",
    # Angelman syndrome – Harry Angelman
    "Angelman",
    # Angelucci syndrome – Arnaldo Angelucci
    "Angelucci",
    # Anton–Babinski syndrome (a.k.a. Anton syndrome) – Gabriel Anton, Joseph Babinski
    "Anton–Babinski",
    # Apert syndrome – Eugène Apert
    "Apert",
    # Aran–Duchenne disease (a.k.a. Aran–Duchenne spinal muscular atrophy) – François-Amilcar Aran, Guillaume Duchenne
    "Aran–Duchenne",
    # Armanni–Ebstein nephropathic change – Luciano Armanni, Wilhelm Ebstein
    "Armanni–Ebstein",
    # Arnold–Chiari malformation – Julius Arnold, Hans Chiari
    "Arnold–Chiari",
    # Arthus phenomenon – Nicolas Maurice Arthus
    "Arthus",
    # Asherman syndrome – Joseph G. Asherman
    "Asherman",
    # Asperger syndrome (a.k.a. Asperger disorder) – Hans Asperger
    "Asperger",
    # Avellis syndrome – Georg Avellis
    "Avellis",
    # Ayerza–Arrillaga syndrome (a.k.a. Ayerza–Arrillaga disease, Ayerza syndrome, Ayerza disease) – Abel Ayerza, Francisco Arrillaga
    "Ayerza–Arrillaga",

    # -------------------------------------------------------------------------
    # B
    # -------------------------------------------------------------------------
    # Baastrup syndrome – Christian Ingerslev Baastrup
    "Baastrup",
    # Babesiosis – Victor Babeş
    # ... noun formed from name that is not itself the name
    # Babington disease – Benjamin Babington
    "Babington",
    # Babinski–Fröhlich syndrome – Joseph Babinski, Alfred Fröhlich
    "Babinski–Fröhlich",
    # Babinski–Froment syndrome – Joseph Babinski, Jules Froment
    "Babinski–Froment",
    # Babinski–Nageotte syndrome – Joseph Babinski, Jean Nageotte
    "Babinski–Nageotte",
    # Baker cyst – William Morrant Baker
    "Baker",
    # Baller–Gerold syndrome – Friedrich Baller, M Gerold
    "Baller–Gerold",
    # Balo concentric sclerosis (a.k.a. Balo disease) – József Mátyás Baló
    "Balo",
    # Bamberger disease – Heinrich von Bamberger
    "Bamberger",
    # Bamberger–Marie disease – Eugen von Bamberger, Pierre Marie
    "Bamberger–Marie",
    # Bancroft filariasis – Joseph Bancroft
    "Bancroft",
    # Bang's disease – Bernhard Bang
    "Bang",
    # Bankart lesion – Arthur Bankart
    "Bankart",
    # Bannayan–Riley–Ruvalcaba syndrome – George A. Bannayan, Harris D. Riley, Jr., Rogelio H. A. Ruvalcaba
    "Bannayan–Riley–Ruvalcaba",
    # Bannayan–Zonana syndrome – George A. Bannayan, Jonathan X. Zonana
    "Bannayan–Zonana",
    # Banti's syndrome – Guido Banti
    "Banti",
    # Bárány syndrome – Robert Bárány
    "Bárány",
    # Bardet–Biedl syndrome (formerly, a.k.a. Laurence–Moon–Bardet–Biedl syndrome, now deemed an invalid synonym) – Georges Bardet, Arthur Biedl
    "Bardet–Biedl",  # other names e.g. under Laurence
    # Barlow disease – Thomas Barlow
    "Barlow",
    # Barlow's syndrome – John Barlow
    "Barlow",
    # Barraquer–Simons syndrome – Luis Barraquer Roviralta, Arthur Simons
    "Barraquer–Simons",
    # Barré–Liéou syndrome – Jean Alexandre Barré, Yang-Choen Liéou
    "Barré–Liéou",
    # Barrett's ulcer – Norman Barrett
    "Barrett",
    # Bart–Pumphrey syndrome – R. S. Bart, R. E. Pumphrey
    "Bart–Pumphrey",
    # Barth syndrome – Peter Barth
    "Barth",
    # Bartholin cyst – Caspar Bartholin
    "Bartholin",
    # Bartter syndrome – Frederic Bartter
    "Bartter",
    # Basedow disease – Karl Adolph von Basedow
    "Basedow",
    # Basedow syndrome – Karl Adolph von Basedow
    "Basedow",
    # Bassen–Kornzweig syndrome – Frank Bassen, Abraham Kornzweig
    "Bassen–Kornzweig",
    # Batten disease – Frederick Batten
    "Batten",
    # Bazin disease – Pierre-Antoine-Ernest Bazin
    "Bazin",
    # Becker muscular dystrophy – Peter Emil Becker
    "Becker",
    # Beckwith–Wiedemann syndrome – John Bruce Beckwith, Hans-Rudolf Wiedemann
    "Beckwith–Wiedemann",
    # Behçet disease – Hulusi Behçet
    "Behçet",
    # Bekhterev disease – Vladimir Bekhterev
    "Bekhterev",
    # Bell palsy – Charles Bell
    "Bell",
    # Benedikt syndrome – Moritz Benedikt
    "Benedikt",
    # Benjamin syndrome – Erich Benjamin
    "Benjamin",
    # Berardinelli–Seip congenital lipodystrophy – W Berardinelli, M Seip
    "Berardinelli–Seip",
    # Berdon syndrome – Walter Berdon
    "Berdon",
    # Berger disease – Jean Berger
    "Berger",
    # Bergeron disease – Etienne-Jules Bergeron
    "Bergeron",
    # Bernard syndrome – Claude Bernard
    "Bernard",
    # Bernard–Soulier syndrome – Jean Bernard, Jean Pierre Soulier
    "Bernard–Soulier",
    # Bernhardt–Roth paraesthesia – Martin Bernhardt, Vladimir Karlovich Roth
    "Bernhardt–Roth",
    # Bernheim syndrome – P. I. Bernheim
    "Bernheim",
    # Besnier prurigo – Ernest Henri Besnier
    "Besnier",
    # Besnier–Boeck–Schaumann disease – Ernest Henri Besnier, Cæsar Peter Møller Boeck, Jörgen Nilsen Schaumann
    "Besnier–Boeck–Schaumann",
    # Biermer anaemia – Michael Anton Biermer
    "Biermer",
    # Bietti crystalline dystrophy – G. Bietti
    "Bietti",
    # Bickerstaff brainstem encephalitis – Edwin Bickerstaff
    "Bickerstaff",
    # Bilharzia – Theodor Maximilian Bilharz
    # ... the disease is its own noun, not the name
    # Binder syndrome – K.H. Binder
    "Binder",
    # Bing–Horton syndrome – Paul Robert Bing, Bayard Taylor Horton
    "Bing–Horton",
    # Bing–Neel syndrome – Jens Bing, Axel Valdemar Neel
    "Bing–Neel",
    # Binswanger dementia – Otto Binswanger
    "Binswanger",
    # Birt–Hogg–Dubé syndrome – Arthur Birt, Georgina Hogg, William Dubé
    "Birt–Hogg–Dubé",
    # Bland–White–Garland syndrome – Edward Franklin Bland, Paul Dudley White, Joseph Garland
    "Bland–White–Garland",
    # Bloch–Sulzberger syndrome – Bruno Bloch, Marion Baldur Sulzberger
    "Bloch–Sulzberger",
    # Bloom syndrome – David Bloom
    "Bloom",
    # Blount syndrome – Walter Putnam Blount
    "Blount",
    # Boerhaave syndrome – Herman Boerhaave
    "Boerhaave",
    # Bogorad syndrome – F. A. Bogorad
    "Bogorad",
    # Bonnevie–Ullrich syndrome – Kristine Bonnevie, Otto Ullrich
    "Bonnevie–Ullrich",
    # Bourneville–Pringle disease – Désiré-Magloire Bourneville, John James Pringle
    "Bourneville–Pringle",
    # Bowen disease – John T. Bowen
    "Bowen",
    # Brachman de Lange syndrome – Winfried Robert Clemens Brachmann, Cornelia Catharina de Lange
    "Brachman–de Lange",
    # Brailsford–Morquio syndrome – James Frederick Brailsford, Luís Morquio
    "Brailsford–Morquio",
    # Brandt syndrome – Thore Edvard Brandt
    "Brandt",
    # Brenner tumour – Fritz Brenner
    "Brenner",
    # Brewer kidney – George Emerson Brewer
    "Brewer",
    # Bright disease – Richard Bright
    "Bright",
    # Brill–Symmers disease – Nathan Brill, Douglas Symmers
    "Brill–Symmers",
    # Brill–Zinsser disease – Nathan Brill, Hans Zinsser
    "Brill–Zinsser",
    # Briquet syndrome – Paul Briquet
    "Briquet",
    # Brissaud disease – Édouard Brissaud
    "Brissaud",
    # Brissaud–Sicard syndrome – Édouard Brissaud, Jean-Athanase Sicard
    "Brissaud–Sicard",
    # Broadbent apoplexy – William Broadbent
    "Broadbent",
    # Brock syndrome – Russell Claude Brock
    "Brock",
    # Brodie abscess – Benjamin Collins Brodie
    "Brodie",
    # Brodie syndrome – Benjamin Collins Brodie
    "Brodie",
    # Brooke epithelioma – Henry Ambrose Grundy Brooke
    "Brooke",
    # Brown-Séquard syndrome – Charles-Édouard Brown-Séquard
    "Brown-Séquard",
    # Brucellosis – David Bruce
    # ... its own noun
    # Bruck–de Lange disease – Franz Bruck, Cornelia Catharina de Lange
    "Bruck–de Lang",
    # Brugada syndrome – Pedro Brugada, Josep Brugada
    "Brugada",
    # Bruns syndrome – Ludwig Bruns
    "Bruns",
    # Bruton–Gitlin syndrome – Ogden Carr Bruton, David Gitlin
    "Bruton–Gitlin",
    # Budd–Chiari syndrome – George Budd, Hans Chiari
    "Budd–Chiari",
    # Buerger disease – Leo Buerger
    "Buerger",
    # Bumke syndrome – Oswald Conrad Edouard Bumke
    "Bumke",
    # Bürger–Grütz syndrome – Max Burger, Otto Grutz
    "Bürger–Grütz",
    # Burkitt lymphoma – Denis Parsons Burkitt
    "Burkitt",
    # Burnett syndrome – Charles Hoyt Burnett
    "Burnett",
    # Bywaters syndrome – Eric Bywaters
    "Bywaters",

    # -------------------------------------------------------------------------
    # C
    # -------------------------------------------------------------------------
    # Caffey–Silverman syndrome – John Patrick Caffey, William Silverman
    "Caffey–Silverman",
    # Calvé disease – Jacques Calvé
    "Calvé",
    # Camurati–Engelmann disease (a.k.a. Camurati–Engelmann syndrome, Engelmann disease, Engelmann syndrome) – M. Camurati, G. Engelmann
    "Camurati–Engelmann",
    # Canavan disease – Myrtelle Canavan
    "Canavan",
    # Cannon disease – Walter Cannon
    "Cannon",
    # Cantú syndrome – José María Cantú
    "Cantú",
    # Capgras delusion (a.k.a. Capgras syndrome) – Joseph Capgras
    "Capgras",
    # Caplan's syndrome – Anthony Caplan
    "Caplan",
    # Carney complex – J. Aidan Carney
    "Carney",
    # Carney triad – J. Aidan Carney
    "Carney",
    # Carney–Stratakis syndrome – J. Aidan Carney, C. A. Stratakis
    "Carney–Stratakis",
    # Caroli syndrome – Jacques Caroli
    "Caroli",
    # Carrión's disease – Daniel Alcides Carrión
    "Carrión",
    # Castleman disease – Benjamin Castleman
    "Castleman",
    # Céstan–Chenais syndrome – Étienne Jacques Marie Raymond Céstan, Louis Jean Chennais
    "Céstan–Chenais",
    # Chagas disease – Carlos Chagas
    "Chagas",
    # Charcot's disease – Jean-Martin Charcot
    "Charcot",
    # Charcot–Marie–Tooth disease – Jean-Martin Charcot, Pierre Marie, Howard Henry Tooth
    "Charcot–Marie–Tooth",
    # Charles Bonnet syndrome – Charles Bonnet
    "Charles Bonnet"
    # Cheadle's disease – Walter Butler Cheadle
    "Cheadle",
    # Chédiak–Higashi syndrome – Alexander Chédiak, Otokata Higashi
    "Chédiak–Higashi",
    # Chiari malformation – Hans Chiari
    "Chiari",
    # Chiari–Frommel syndrome – Johann Baptist Chiari, Richard Frommel
    "Chiari–Frommel",
    # Chilaiditi syndrome – Demetrius Chilaiditi
    "Chilaiditi",
    # Christ–Siemens–Touraine syndrome – Josef Christ, Hermann Werner Siemens, Albert Touraine
    "Christ–Siemens–Touraine",
    # Christensen–Krabbe disease – Erna Christensen, Knud Krabbe
    "Christensen–Krabbe",
    # Christmas disease – Stephen Christmas
    "Christmas",
    # Churg–Strauss syndrome – Jacob Churg, Lotte Strauss
    "Churg–Strauss",
    # Claude syndrome – Henri Claude
    "Claude",
    # Claude Bernard–Horner syndrome – Claude Bernard, Johann Friedrich Horner
    "Claude Bernard–Horner",
    # Clerambault syndrome – Gaëtan Gatian de Clerambault
    "Clerambault",
    # Clerambault–Kandinsky syndrome – Gaëtan Gatian de Clerambault, Victor Khrisanfovich Kandinsky
    "Clerambault–Kandinsky",
    # Coats' disease – George Coats
    "Coats",
    # Cock's peculiar tumour – Edward Cock
    "Cock",
    # Cockayne syndrome – Edward Alfred Cockayne
    "Cockayne",
    # Coffin–Lowry syndrome – Grange Coffin, Robert Lowry
    "Coffin–Lowry",
    # Coffin–Siris syndrome – Grange Coffin, Evelyn Siris
    "Coffin–Siris",
    # Cogan's syndrome – David Glendenning Cogan
    "Cogan",
    # Cohen syndrome – Michael Cohen
    "Cohen",
    # Collet–Sicard syndrome – Frédéric Justin Collet, Jean-Athanase Sicard
    "Collet–Sicard",
    # Concato disease – Luigi Maria Concato
    "Concato",
    # Conn's syndrome – Jerome Conn
    "Conn",
    # Cooley's anemia – Thomas Benton Cooley
    "Cooley",
    # Cori Disease – Carl Ferdinand Cori, Gerty Cori
    "Cori",
    # Cornelia de Lange syndrome – Cornelia Catharina de Lange
    "Cornelia de Lange",
    # Costello syndrome – Jack Costello
    "Costello",
    # Costen syndrome – James Bray Costen
    "Costen",
    # Cotard's Syndrome – Jules Cotard
    "Cotard",
    # Cowden's syndrome (a.k.a. Cowden's disease) – Rachel Cowden
    "Cowden",
    # Crigler–Najjar syndrome – John Fielding Crigler, Victor Assad Najjar
    "Crigler–Najjar",
    # Creutzfeldt–Jakob disease – Hans Gerhard Creutzfeldt, Alfons Maria Jakob
    "Creutzfeldt–Jakob",
    # Crocq–Cassirer syndrome – Jean Crocq, Richard Cassirer
    "Crocq–Cassirer",
    # Crohn's disease – Burrill Bernard Crohn
    "Crohn",
    # Cronkhite–Canada syndrome – L. W. Cronkhite, Wilma Canada
    "Cronkhite–Canada",
    # Crouzon syndrome – Octave Crouzon
    "Crouzon",
    # Cruveilhier–Baumgarten disease – Jean Cruveilhier, Paul Clemens von Baumgarten
    "Cruveilhier–Baumgarten",
    # Cruz disease – Osvaldo Gonçalves Cruz
    "Cruz",
    # Curling's ulcer – Thomas Blizard Curling
    "Curling",
    # Curschmann–Batten–Steinert syndrome – Hans Curschmann, Frederick Batten, Hans Gustav Steinert
    "Curschmann–Batten–Steinert",
    # Cushing's disease – Harvey Cushing
    "Cushing",
    # Cushing's ulcer – Harvey Cushing
    "Cushing",

    # -------------------------------------------------------------------------
    # D
    # -------------------------------------------------------------------------
    # Da Costa syndrome – Jacob Mendez Da Costa
    "Da Costa",
    # Dalrymple disease – John Dalrymple
    "Dalrymple",
    # Danbolt–Closs syndrome – Niels Christian Gauslaa Danbolt, Karl Philipp Closs
    "Danbolt–Closs",
    # Dandy–Walker syndrome – Walter Dandy, Arthur Earl Walker
    "Dandy–Walker",
    # De Clérambault syndrome – Gaëtan Gatian de Clérambault
    "de Clérambault",
    # de Quervain disease – Fritz de Quervain
    "de Quervain",
    # de Quervain thyroiditis – Fritz de Quervain
    "de Quervain",
    # Dejerine–Sottas disease – Joseph Jules Dejerine, Jules Sottas
    "Dejerine–Sottas",
    # Dennie–Marfan syndrome – Charles Clayton Dennie, Antoine Marfan
    "Dennie–Marfan",
    # Dent disease – Charles Enrique Dent
    "Dent",
    # Denys–Drash syndrome – Pierre Denys, Allan L. Drash
    "Denys–Drash",
    # Dercum disease – Francis Xavier Dercum
    "Dercum",
    # Devic disease (a.k.a. Devic syndrome) – Eugène Devic
    "Devic",
    # Diamond–Blackfan anemia – Louis Diamond, Kenneth Blackfan
    "Diamond–Blackfan",
    # DiGeorge syndrome – Angelo DiGeorge
    "DiGeorge",
    # Di Guglielmo disease – Giovanni di Gugliemo
    "Di Guglielmo",
    # Diogenes syndrome (a.k.a. Havisham syndrome, Miss Havisham syndrome, Plyushkin syndrome)– Diogenes of Sinope (the particular usage, Diogenes syndrome, is deemed to be a misnomer)
    "Diogenes",
    # Doege–Potter syndrome – Karl W. Doege, Roy P. Potter
    "Doege–Potter",
    # Donnai–Barrow syndrome – Dian Donnai, Margaret Barrow
    "Donnai–Barrow",
    # Donovanosis – Charles Donovan
    "Donovanosis",
    # Down syndrome – John Langdon Down
    "Down",
    # Dravet syndrome – Charlotte Dravet
    "Dravet",
    # Dressler syndrome – William Dressler
    "Dressler",
    # Duane syndrome – Alexander Duane
    "Duane",
    # Dubin–Johnson syndrome
    "Dubin–Johnson",
    # Duchenne–Aran disease – Guillaume-Benjamin-Amand Duchenne de Boulogne, François-Amilcar Aran
    "Duchenne–Aran",
    # Duchenne muscular dystrophy – Guillaume-Benjamin-Amand Duchenne de Boulogne
    "Duchenne",
    # Dukes disease – Clement Dukes
    "Dukes",
    # Duncan disease (a.k.a. Duncan syndrome, Purtilo syndrome) – David Theodore Purtilo
    "Duncan",
    # Dupuytren contracture (a.k.a. Dupuytren disease) – Baron Guillaume Dupuytren
    "Dupuytren",
    # Duroziez disease – Paul Louis Duroziez
    "Duroziez",

    # -------------------------------------------------------------------------
    # E
    # -------------------------------------------------------------------------
    # Eales disease – Henry Eales
    "Eales",
    # Early-onset Alzheimer disease – Alois Alzheimer
    "Alzheimer",
    # Ebstein's anomaly – Wilhelm Ebstein
    "Ebstein",
    # Edwards syndrome – John H. Edwards
    "Edwards",
    # Ehlers–Danlos syndrome – Edvard Ehlers, Henri-Alexandre Danlos
    "Ehlers–Danlos",
    # Ehrlichiosis – Paul Ehrlich
    # ... noun, not name
    # Eisenmenger's syndrome – Victor Eisenmenger
    "Eisenmenger",
    # Ekbom's Syndrome – Karl-Axel Ekbom
    "Ekbom",
    # Emanuel syndrome – Beverly Emanuel
    "Emanuel",
    # Emery–Dreifuss muscular dystrophy – Alan Eglin H. Emery, Fritz E. Dreifuss
    "Emery–Dreifuss",
    # Erb–Duchenne palsy (a.k.a. Erb palsy) – Wilhelm Heinrich Erb, Guillaume-Benjamin-Amand Duchenne de Boulogne
    "Erb–Duchenne",
    # Erdheim–Chester disease – Jakob Erdheim, William Chester
    "Erdheim–Chester",
    # Evans syndrome – R. S. Evans
    "Evans",
    # Extramammary Paget's disease – Sir James Paget
    "Paget",

    # -------------------------------------------------------------------------
    # F
    # -------------------------------------------------------------------------
    # Fabry disease – Johannes Fabry
    "Fabry",
    # Fanconi anemia – Guido Fanconi
    "Fanconi",
    # Fanconi syndrome – Guido Fanconi
    "Fanconi",
    # Farber disease – Sidney Farber
    "Farber",
    # Felty's syndrome – Augustus Roi Felty
    "Felty",
    # Fitz-Hugh–Curtis syndrome – Thomas Fitz-Hugh Jr., Arthur Hale Curtis
    "Fitz-Hugh–Curtis",
    # Foix–Alajouanine syndrome – Charles Foix, Théophile Alajouanine
    "Foix–Alajouanine",
    # Fournier gangrene – Jean Alfred Fournier
    "Fournier",
    # Forbes–Albright syndrome – Anne E. Forbes, Fuller Albright
    "Forbes–Albright",
    # WAS: Forbe's Disease – Gilbert Burnett Forbes
    # ... typo in Wikipedia; name is Forbes; FIXED 2018-03-27
    # ... see also https://rarediseases.org/rare-diseases/forbes-disease/
    "Forbes",
    # Fregoli delusion – Leopoldo Fregoli, an Italian actor
    "Fregoli",
    # Frey's syndrome - Lucja Frey-Gottesman, Jewish neurosurgeon
    "Frey",
    # Friedreich's ataxia – Nikolaus Friedreich
    "Friedreich",
    # Fritsch–Asherman syndrome (a.k.a. Fritsch syndrome) – Heinrich Fritsch, Joseph Asherman
    "Fritsch–Asherman",
    # Fuchs' dystrophy – Ernst Fuchs
    "Fuchs",

    # -------------------------------------------------------------------------
    # G
    # -------------------------------------------------------------------------
    # Ganser syndrome – Sigbert Ganser
    "Ganser",
    # Gaucher's disease – Philippe Gaucher
    "Gaucher",
    # Gerbec–Morgagni–Adams–Stokes syndrome (a.k.a. Adams–Stokes syndrome, Gerbezius–Morgagni–Adams–Stokes syndrome, Stokes–Adams syndrome) – Marko Gerbec, Giovanni Battista Morgagni, Robert Adams, William Stokes
    "Gerbec–Morgagni–Adams–Stokes",
    # Gerbezius–Morgagni–Adams–Stokes syndrome (a.k.a. Adams–Stokes syndrome, Gerbec–Morgagni–Adams–Stokes syndrome, Stokes–Adams syndrome) – Marko Gerbec (Latinized as Gerbezius), Giovanni Battista Morgagni, Robert Adams, William Stokes
    "Gerbezius–Morgagni–Adams–Stokes",
    # Ghon's complex – Anton Ghon
    "Ghon",
    # Ghon focus – Anton Ghon
    "Ghon",
    # Gilbert syndrome – Augustin Nicolas Gilbert
    "Gilbert",
    # Gitelman syndrome – Hillel J. Gitelman
    "Gitelman",
    # Glanzmann's thrombasthenia – Eduard Glanzmann
    "Glanzmann",
    # Goodpasture's syndrome – Ernest Goodpasture
    "Goodpasture",
    # Goldenhar syndrome – Maurice Goldenhar
    "Goldenhar",
    # Gorlin–Goltz syndrome – Robert J. Gorlin, Robert W. Goltz
    "Gorlin–Goltz",
    # Gouverneur’s syndrome – R. Gouverneur
    "Gouverneur",
    # Graves' disease – Robert James Graves
    "Graves",
    # Graves–Basedow disease – Robert James Graves, Karl Adolph von Basedow
    "Graves–Basedow",
    # Grawitz tumor – Paul Albert Grawitz
    "Grawitz",
    # Grinker myelinopathy – Roy R. Grinker, Sr.
    "Grinker",
    # Gruber syndrome – Georg Gruber
    "Gruber",
    # Guillain–Barré syndrome – Georges Guillain, Jean Alexandre Barré
    "Guillain–Barré",
    # Gunther's disease – Hans Gunther
    "Gunther",

    # -------------------------------------------------------------------------
    # H
    # -------------------------------------------------------------------------
    # Hailey–Hailey disease – Hugh Edward Hailey, William Howard Hailey
    "Hailey–Hailey",
    # Hallervorden–Spatz disease – Julius Hallervorden, Hugo Spatz
    "Hallervorden–Spatz",
    # Hand–Schüller–Christian disease – Alfred Hand, Artur Schüller, Henry Asbury Christian
    "Hand–Schüller–Christian",
    # Hansen's disease – Gerhard Armauer Hansen
    "Hansen",
    # Hardikar Syndrome – Winita Hardikar
    "Hardikar",
    # Hartnup disease (a.k.a. Hartnup disorder) – Hartnup family of London, U.K.
    "Hartnup",
    # Hashimoto thyroiditis – Hakaru Hashimoto
    "Hashimoto",
    # Havisham syndrome (a.k.a. Diogenes syndrome, Miss Havisham syndrome, and Plyushkin syndrome) – Miss Havisham, a fictional character in Charles Dickens' Great Expectations
    "Havisham",
    # Hecht–Scott syndrome – Jacqueline T. Hecht, Charles I. Scott, Jr
    "Hecht–Scott",
    # Henoch–Schönlein purpura – Eduard Heinrich Henoch, Johann Lukas Schönlein
    "Henoch–Schönlein",
    # Heyde's syndrome – Edward C. Heyde
    "Heyde",
    # Hirschsprung disease – Harald Hirschsprung
    "Hirschsprung",
    # Hodgkin disease – Thomas Hodgkin
    "Hodgkin",
    # Holt–Oram syndrome – Mary Clayton Holt, Samuel Oram
    "Holt–Oram",
    # Horner syndrome – Johann Friedrich Horner
    "Horner",
    # Horton headache – Bayard Taylor Horton
    "Horton",
    # Huntington's disease – George Huntington
    "Huntington",
    # Hurler syndrome – Gertrud Hurler
    "Hurler",
    # Hurler–Scheie syndrome – Gertrud Hurler, Harold Glendon Scheie
    "Hurler–Scheie",
    # Hutchinson–Gilford progeria syndrome – Jonathan Hutchinson, Hastings Gilford
    "Hutchinson–Gilford",

    # -------------------------------------------------------------------------
    # I
    # -------------------------------------------------------------------------
    # Illig syndrome – Ruth Illig
    "Illig",
    # Irvine–Gass syndrome – S. Rodman Irvine, J. Donald M. Gass
    "Irvine–Gass",

    # -------------------------------------------------------------------------
    # J
    # -------------------------------------------------------------------------
    # Jaeken's disease – Jaak Jaeken
    "Jaeken",
    # Jakob–Creutzfeldt disease – Alfons Maria Jakob, Hans Gerhard Creutzfeldt
    "Jakob–Creutzfeldt",
    # Jarvi–Nasu–Hakola disease – O. Jarvi, T. Nasu, P. Hakola
    "Jarvi–Nasu–Hakola",
    # Johanson–Blizzard syndrome – Ann Johanson, Robert M. Blizzard
    "Johanson–Blizzard",
    # Julian syndrome – Frankie Julian, Ron Kendall, Abe Charara
    "Julian",

    # -------------------------------------------------------------------------
    # K
    # -------------------------------------------------------------------------
    # Kahler's disease – Otto Kahler
    "Kahler",
    # Kallmann syndrome – Franz Josef Kallmann
    "Kallmann",
    # Kanner syndrome – Leo Kanner
    "Kanner",
    # Kaposi sarcoma – Moritz Kaposi
    "Kaposi",
    # Kartagener syndrome – Manes Kartagener
    "Kartagener",
    # Kasabach–Merritt syndrome – Haig Haigouni Kasabach, Katharine Krom Merritt
    "Kasabach–Merritt",
    # Kashin–Beck disease – Nicolai Ivanowich Kashin, Evgeny Vladimirovich Bek
    "Kashin–Beck",
    # Kawasaki disease – Tomisaku Kawasaki
    "Kawasaki",
    # Kearns–Sayre syndrome – Thomas P. Kearns, George Pomeroy Sayre
    "Kearns–Sayre",
    # Kennedy's disease – William R. Kennedy
    "Kennedy",
    # Kennedy's syndrome – Robert Foster Kennedy
    "Kennedy",
    # Kenny syndrome – Frederic Marshal Kenny
    "Kenny",
    # Kienbock's disease – Robert Kienböck
    "Kienbock",
    # Kikuchi's disease – Masahiro Kikuchi, Y.Fujimoto
    "Kikuchi",
    # Kimmelstiel–Wilson disease – Paul Kimmelstiel, Clifford Wilson
    "Kimmelstiel–Wilson",
    # Kimura's disease – T. Kimura
    "Kimura",
    # King–Kopetzky syndrome – P. F. King, Samuel J. Kopetzky
    "King–Kopetzky",
    # Kinsbourne syndrome – Marcel Kinsbourne
    "Kinsbourne",
    # Kjer's optic neuropathy – Poul Kjer
    "Kjer",
    # Klatskin's tumor – Gerald Klatskin
    "Klatskin",
    # Klinefelter syndrome – Harry Klinefelter
    "Klinefelter",
    # Klüver–Bucy syndrome – Heinrich Klüver, Paul Bucy
    "Klüver–Bucy",
    # Köhler disease – Alban Köhler
    "Köhler",
    # Korsakoff syndrome – Sergei Korsakoff
    "Korsakoff",
    # Kounis syndrome – Nicholas Kounis
    "Kounis",
    # Krabbe's disease – Knud Haraldsen Krabbe
    "Krabbe",
    # Krukenberg tumor – Friedrich Ernst Krukenberg
    "Krukenberg",
    # Kugelberg–Welander disease – Erik Klas Henrik Kugelberg, Lisa Welander
    "Kugelberg–Welander",
    # Kuttner's tumor – Hermann Küttner
    "Kuttner",

    # -------------------------------------------------------------------------
    # L
    # -------------------------------------------------------------------------
    # Lafora's disease – Gonzalo Rodriguez Lafora
    "Lafora",
    # Laron syndrome – Zvi Laron
    "Laron",
    # Laurence–Moon syndrome – John Zachariah Laurence, Robert Charles Moon
    "Laurence–Moon",
    # Laurence–Moon–Bardet–Biedl syndrome (a.k.a. Laurence–Moon–Biedl–Bardet syndrome, a.k.a. Laurence–Moon–Biedl syndrome) – John Zachariah Laurence, Robert Charles Moon, Georges Bardet, Arthur Biedl – all now deemed invalid constructs, see instead Bardet–Biedl syndrome
    "Laurence–Moon–Bardet–Biedl",
    # Legg–Calvé–Perthes syndrome – Arthur Legg, Jacques Calvé, Georg Perthes
    "Legg–Calvé–Perthes",
    # Leigh's disease – Denis Archibald Leigh
    "Leigh",
    # Leiner syndrome – Karl Leiner, André Moussous
    "Leiner",
    # Leishmaniasis – Sir William Boog Leishman
    # ... noun, not name
    # Lejeune’s syndrome – Jérôme Lejeune
    "Lejeune",
    # Lemierre's syndrome – André Lemierre
    "Lemierre",
    # Lenègre's disease – Jean Lenègre
    "Lenègre",
    # Lesch–Nyhan syndrome – Michael Lesch, William Leo Nyhan
    "Lesch–Nyhan",
    # Letterer–Siwe disease – Erich Letterer, Sture Siwe
    "Letterer–Siwe",
    # Lev's disease – Maurice Lev, Jean Lenègre
    "Lev",
    # Lewandowsky–Lutz dysplasia – Felix Lewandowsky, Wilhelm Lutz
    "Lewandowsky–Lutz",
    # Li–Fraumeni syndrome – Frederick Pei Li, Joseph F. Fraumeni, Jr.
    "Li–Fraumeni",
    # Libman–Sacks disease – Emanuel Libman, Benjamin Sacks
    "Libman–Sacks",
    # Liddle's syndrome – Grant Liddle
    "Liddle",
    # Lisfranc injury (a.k.a. Lisfranc dislocation, a.k.a. Lisfranc fracture) – Jacques Lisfranc de St. Martin
    "Lisfranc",
    # Listeriosis – Joseph Lister
    # ... noun, not name
    # Lobomycosis – Jorge Lobo
    # ... noun, not name
    # Löffler's eosinophilic endocarditis – Wilhelm Löffler
    "Löffler",
    # Löfgren syndrome – Sven Halvar Löfgren
    "Löfgren",
    # Lou Gehrig's disease – Lou Gehrig
    "Lou Gehrig",
    # Lowe Syndrome – Charles Upton Lowe
    "Lowe",
    # Ludwig's angina – Wilhelm Friedrich von Ludwig
    "Ludwig",
    # Lynch syndrome – Henry T. Lynch
    "Lynch",

    # -------------------------------------------------------------------------
    # M
    # -------------------------------------------------------------------------
    # Machado–Joseph disease (a.k.a. Machado–Joseph Azorean disease, Machado disease, Joseph's disease) – named for William Machado and Antone Joseph, patriarchs of families in which it was first identified
    "Machado–Joseph",
    # Marie–Foix–Alajouanine syndrome – Pierre Marie, Charles Foix, Théophile Alajouanine
    "Marie–Foix–Alajouanine",
    # Maladie de Charcot – Jean-Martin Charcot
    "Charcot",
    # Mallory–Weiss syndrome – G. Kenneth Mallory, Soma Weiss
    "Mallory–Weiss",
    # Mansonelliasis – Sir Patrick Manson
    # ... noun, not name
    # Marburg multiple sclerosis – Otto Marburg
    "Marburg",
    # Marfan syndrome – Antoine Marfan
    "Marfan",
    # Marshall syndrome – Richard E. Marshall
    "Marshall",
    # Marshall–Smith–Weaver syndrome (a.k.a. Marshall–Smith syndrome, Greig syndrome) – Richard E. Marshall, David Weyhe Smith
    "Marshall–Smith–Weaver",
    "Greig",  # not otherwise listed; it is a person; https://www.omim.org/entry/175700
    # Martin–Albright syndrome (a.k.a. Albright IV syndrome) – August E. Martin, Fuller Albright
    "Martin–Albright",
    # May–Hegglin anomaly – Richard May, Robert Hegglin
    "May–Hegglin",
    # Maydl's hernia — Karel Maydl
    "Maydl",
    # Mazzotti reaction – Luigi Mazzotti
    "Mazzotti",
    # McArdle's Disease – Brian McArdle
    "McArdle",
    # McCune–Albright syndrome – Donovan James McCune, Fuller Albright
    "McCune–Albright",
    # Meckel–Gruber syndrome (a.k.a. Meckel syndrome) – Johann Meckel, Georg Gruber
    "Meckel–Gruber",
    # Meigs' syndrome – Joe Vincent Meigs
    "Meigs",
    # Ménétrier's disease – Pierre Eugène Ménétrier
    "Ménétrier",
    # Ménière’s disease – Prosper Ménière
    "Ménière",
    # Menkes disease – John Hans Menkes
    "Menkes",
    # Middleton syndrome – Stephen John Middleton
    "Middleton",
    # Mikulicz's disease – Jan Mikulicz-Radecki
    "Mikulicz",
    # Miss Havisham syndrome (a.k.a. Diogenes syndrome, Havisham syndrome, and Plyushkin syndrome) – Miss Havisham, a fictional character in Charles Dickens' Great Expectations
    "Havisham",
    # Mondor's disease – Henri Mondor
    "Mondor",
    # Monge's disease – Carlos Monge
    "Monge",
    # Mortimer's disease – First documented by Jonathan Hutchinson, named for his patient Mrs. Mortimer
    "Mortimer",
    # Moschcowitz syndrome – Eli Moschcowitz
    "Moschcowitz",
    # Mowat–Wilson syndrome – David Mowat, Meredith Wilson
    "Mowat–Wilson",
    # Mucha–Habermann disease – Viktor Mucha, Rudolf Habermann
    "Mucha–Habermann",
    # Mulvihill–Smith syndrome – John J. Mulvihill, David Weyhe Smith
    "Mulvihill–Smith",
    # Munchausen syndrome – Baron Munchausen
    "Munchausen",
    # Munchausen syndrome by proxy – Baron Munchausen
    # Myhre–Riley–Smith syndrome – S. Myhre, Harris D. Riley, Jr.
    "Myhre–Riley–Smith",

    # -------------------------------------------------------------------------
    # N
    # -------------------------------------------------------------------------
    # Nasu–Hakola disease – T. Nasu, P. Hakola
    "Nasu–Hakola",
    # Non-Hodgkin's lymphoma – Thomas Hodgkin
    "Hodgkin",
    # Noonan syndrome – Jacqueline Noonan
    "Noonan",

    # -------------------------------------------------------------------------
    # O
    # -------------------------------------------------------------------------
    # Ormond's disease – John Kelso Ormond
    "Ormond",
    # Osgood–Schlatter disease – Robert Bayley Osgood, Carl B. Schlatter
    "Osgood–Schlatter",
    # Osler–Weber–Rendu syndrome – William Osler, Frederick Parkes Weber, Henri Jules Louis Marie Rendu
    "Osler–Weber–Rendu",

    # -------------------------------------------------------------------------
    # P
    # -------------------------------------------------------------------------
    # Paget's disease of bone (a.k.a. Paget's disease) – James Paget
    # Paget's disease of the breast (a.k.a. Paget's disease of the nipple) – James Paget
    # Paget's disease of the penis – James Paget
    # Paget's disease of the vulva – James Paget
    "Paget",
    # Paget–Schroetter disease (a.k.a. Paget–Schroetter syndrome and Paget–von Schrötter disease) – James Paget, Leopold von Schrötter
    "Paget–Schroetter",
    # Parkinson's disease – James Parkinson
    "Parkinson",
    # Patau syndrome – Klaus Patau
    "Patau",
    # Pearson syndrome – Howard Pearson
    "Pearson",
    # Pelizaeus–Merzbacher disease – Friedrich Christoph Pelizaeus, Ludwig Merzbacher
    "Pelizaeus–Merzbacher",
    # Perthes syndrome – Arthur Legg, Jacques Calvé, Georg Perthes
    "Perthes",
    # Peutz–Jeghers syndrome – Jan Peutz, Harold Jeghers
    "Peutz–Jeghers",
    # Peyronie's disease – François Gigot de la Peyronie
    "Peyronie",
    # Pfaundler–Hurler syndrome – Meinhard von Pfaundler, Gertrud Hurler
    "Pfaundler–Hurler",
    # Pick's disease – Arnold Pick
    "Pick",
    # Pickardt syndrome – C. R. Pickardt
    "Pickardt",
    # Plummer's disease – Henry Stanley Plummer
    "Plummer",
    # Plummer–Vinson syndrome (a.k.a. Kelly–Patterson syndrome, Paterson–Brown–Kelly syndrome, and Waldenstrom–Kjellberg syndrome) – Henry Stanley Plummer and Porter Paisley Vinson
    "Plummer–Vinson",
    # Plyushkin syndrome (a.k.a. Diogenes syndrome, Havisham syndrome, and Miss Havisham syndrome)– Stepan Plyushkin, a fictional character in Nikolai Gogol's Dead Souls
    "Plyushkin",
    # Poland's syndrome – Alfred Poland
    "Poland",
    # Pompe's disease – Johann Cassianius Pompe
    "Pompe",
    # Pott's disease – Percivall Pott
    # Pott's puffy tumor – Percivall Pott
    "Pott",
    # Potocki–Lupski syndrome – Lorraine Potocki, James R. Lupski
    "Potocki–Lupski",
    # Potocki–Shaffer syndrome – Lorraine Potocki, Lisa G. Shaffer
    "Potocki–Shaffer",
    # Potter sequence – Edith Potter
    "Potter",
    # Prader–Willi syndrome – Andrea Prader, Heinrich Willi
    "Prader–Willi",
    # Prasad's Syndrome – Ashok Prasad
    "Prasad",
    # Primrose syndrome – D. A. Primrose
    "Primrose",
    # Prinzmetal angina – Myron Prinzmetal
    "Prinzmetal",
    # Purtilo syndrome (a.k.a. Duncan disease and Duncan syndrome) –
    "Purtilo",

    # -------------------------------------------------------------------------
    # Q
    # -------------------------------------------------------------------------
    # Quarelli syndrome – G.Quarelli
    "Quarelli",

    # -------------------------------------------------------------------------
    # R
    # -------------------------------------------------------------------------
    # Ramsay Hunt syndrome – James Ramsay Hunt
    "Ramsay Hunt",
    # Ranke complex – Karl Ernst Ranke
    "Ranke",
    # Raymond Céstan syndrome – Étienne Jacques Marie Raymond Céstan
    "Raymond Céstan",
    # Raynaud's disease – Maurice Raynaud
    "Raynaud",
    # Refsum's disease – Sigvald Bernhard Refsum
    "Refsum",
    # Reiter's syndrome – Hans Conrad Julius Reiter (This is now a discouraged eponym due to Dr. Reiter's Nazi party ties. The disease is now known as reactive arthritis.)
    "Reiter",
    # Rett Syndrome – Andreas Rett
    "Rett",
    # Reye's syndrome – R. Douglas Reye
    "Reye",
    # Rickettsiosis – Howard Taylor Ricketts
    # ... noun, not name
    # Riddoch syndrome – Dr. George Riddoch
    "Riddoch",
    # Riedel's thyroiditis – Bernhard Riedel
    "Riedel",
    # Riggs' disease – John M. Riggs (dentist)
    "Riggs",
    # Riley–Day syndrome – Conrad Milton Riley, Richard Lawrence Day
    "Riley–Day",
    # Riley–Smith syndrome – Harris D. Riley, Jr., William R. Smith
    "Riley–Smith",
    # Ritter's disease – Baron Gottfried Ritter von Rittershain
    "Ritter",
    # Robles disease – Rodolfo Robles
    "Robles",
    # Roger's disease – Henri Louis Roger
    "Roger",
    # Rotor syndrome – Arturo Belleza Rotor
    "Rotor",
    # Rubinstein–Taybi syndrome – Jack Herbert Rubinstein, Hooshang Taybi
    "Rubinstein–Taybi",
    # Russell–Silver syndrome – Alexander Russell, Henry Silver
    "Russell–Silver",
    # Ruvalcaba–Myhre syndrome – Rogelio H. A. Ruvalcaba, S. Myhre
    "Ruvalcaba–Myhre",
    # Ruvalcaba–Myhre–Smith syndrome – Rogelio H. A. Ruvalcaba, S. Myhre, David Weyhe Smith
    "Ruvalcaba–Myhre–Smith",
    # Ruzicka–Goerz–Anton syndrome – T. Ruzicka, G. Goerz, I. Anton-Lamprecht
    "Ruzicka–Goerz–Anton",

    # -------------------------------------------------------------------------
    # S
    # -------------------------------------------------------------------------
    # Saint's triad – C. F. M. Saint
    "Saint",
    # Sandhoff disease – Konrad Sandhoff
    "Sandhoff",
    # Sandifer syndrome – Paul Sandifer
    "Sandifer",
    # Schamberg's disease – Jay Frank Schamberg
    "Schamberg",
    # Scheie syndrome – Harold Glendon Scheie
    "Scheie",
    # Scheuermann's disease – Holger Scheuermann
    "Scheuermann",
    # Schilder's disease – Paul Ferdinand Schilder
    "Schilder",
    # Schinzel–Giedion syndrome – Albert Schinzel, Andreas Giedion
    "Schinzel–Giedion",
    # Schnitzler syndrome – Liliane Schnitzler
    "Schnitzler",
    # Seaver Cassidy syndrome – Laurie Seaver, Suzanne Cassidy
    "Seaver–Cassidy"
    # Seligmann's disease – Maxime Seligmann
    "Seligmann",
    # Sever's disease – J. W. Sever
    "Sever",
    # Shabbir syndrome – G. Shabbir
    "Shabbir",
    # Sheehan's syndrome – Harold Leeming Sheehan
    "Sheehan",
    # Shprintzen's syndrome – Robert Shprintzen
    "Shprintzen",
    # Shwachman–Bodian–Diamond syndrome – Harry Shwachman, Martin Bodian, Louis Klein Diamond
    "Shwachman–Bodian–Diamond",
    # Silver–Russell syndrome (a.k.a. Silver–Russell dwarfism) – Henry Silver, Alexander Russell
    "Silver–Russell",
    # Simmonds' syndrome – Moritz Simmonds
    "Simmonds",
    # Sipple's syndrome – John H. Sipple
    "Sipple",
    # Sjögren's syndrome – Henrik Sjögren
    "Sjögren",
    # Sjögren–Larsson syndrome – Torsten Sjögren, Tage Konrad Leopold Larsson
    "Sjögren–Larsson",
    # Smith–Lemli–Opitz syndrome – David Weyhe Smith
    "Smith–Lemli–Opitz",
    # Stargardt disease – Karl Stargardt
    "Stargardt",
    # Steele–Richardson–Olszewski syndrome –
    "Steele–Richardson–Olszewski",
    # Stevens–Johnson syndrome – Albert Mason Stevens, Frank Chambliss Johnson
    "Stevens–Johnson",
    # Sturge–Weber syndrome – William Allen Sturge, Frederick Parkes Weber
    "Sturge–Weber",
    # Still's disease – Sir George Frederic Still
    "Sturge–Weber",
    # Susac's syndrome – John Susac
    "Susac",
    # Sutton's disease – Richard Lightburn Sutton
    "Sutton",

    # -------------------------------------------------------------------------
    # T
    # -------------------------------------------------------------------------
    # TAN syndrome – Tan Aik Kah
    "TAN",
    # ... Odd one! https://en.wikipedia.org/wiki/TAN_syndrome
    # Takayasu's arteritis – Mikito Takayasu
    "Takayasu",
    # Tay–Sachs disease – Warren Tay, Bernard Sachs
    "Tay–Sachs",
    # Theileriosis – Sir Arnold Theiler
    # ... noun, not name
    # Thomsen's disease – Julius Thomsen
    "Thomsen",
    # Tietz syndrome – Walter Tietz
    "Tietz",
    # Tietze's syndrome – Alexander Tietze
    "Tietze",
    # Tourette syndrome – Georges Albert Édouard Brutus Gilles de la Tourette
    "Tourette",
    # Treacher Collins syndrome – Edward Treacher Collins
    "Treacher Collins",
    # Turcot syndrome – Jacques Turcot
    "Turcot",
    # Turner's syndrome – Henry Turner
    "Turner",

    # -------------------------------------------------------------------------
    # U
    # -------------------------------------------------------------------------
    # Unverricht–Lundborg disease – Heinrich Unverricht, Herman Bernhard Lundborg
    "Unverricht–Lundborg",
    # Usher syndrome – Charles Usher
    "Usher",

    # -------------------------------------------------------------------------
    # V
    # -------------------------------------------------------------------------
    # Valentino syndrome – Rudolph Valentino
    "Valentino",
    # Verner Morrison syndrome – J. V. Verner, A. B. Morrison
    "Verner–Morrison",
    # Vincent's angina – Henri Vincent
    "Vincent",
    # Virchow's syndrome – Rudolf Virchow
    "Virchow",
    # Von Gierke's disease – Edgar von Gierke
    "von Gierke",
    # Von Hippel–Lindau disease – Eugen von Hippel, Arvid Vilhelm Lindau
    "von Hippel–Lindau",
    # Von Recklinghausen's disease – Friedrich Daniel von Recklinghausen
    "von Recklinghausen",
    # Von Willebrand's disease – Erik Adolf von Willebrand
    "von Willebrand",

    # -------------------------------------------------------------------------
    # W
    # -------------------------------------------------------------------------
    # Waardenburg syndrome – Petrus Johannes Waardenburg
    "Waardenburg",
    # Waldenstrom–Kjellberg syndrome – Jan G. Waldenström, S. R. Kjellberg
    "Waldenström–Kjellberg",
    # Waldenstrom macroglobulinaemia – Jan G. Waldenström
    "Waldenström",
    # Warkany syndrome 1 – Joseph Warkany
    "Warkany",
    # Warkany syndrome 2 – Joseph Warkany
    "Warkany",
    # Warthin's tumor – Aldred Scott Warthin
    "Warthin",
    # Waterhouse–Friderichsen syndrome – Rupert Waterhouse, Carl Friderichsen
    "Waterhouse–Friderichsen",
    # Watson syndrome – G.H.Watson
    "Watson",
    # Weber–Christian disease – Frederick Parkes Weber, Henry Asbury Christian
    "Weber–Christian",
    # Wegener's granulomatosis – Friedrich Wegener (This usage is now formally discouraged by professional medical societies due to the Nazi associations of the eponymous physician. The disease is now known as granulomatosis with polyangiitis.)
    "Wegener",
    # Weil's disease – Adolf Weil
    "Weil",
    # Welander distal myopathy – Lisa Welander
    "Welander",
    # Wells syndrome – George Crichton Wells
    "Wells",
    # Werdnig–Hoffmann disease – Guido Werdnig, Johann Hoffmann
    "Werdnig–Hoffmann",
    # Wermer's syndrome – Paul Wermer
    "Wermer",
    # Werner's syndrome – Otto Werner
    "Werner",
    # Wernicke's encephalopathy – Karl Wernicke
    "Wernicke",
    # Westerhof syndrome – Wiete Westerhof
    "Westerhof",
    # Westerhof–Beemer–Cormane syndrome – Wiete Westerhof, Frederikus Antonius Beemer, R. H.Cormane
    "Westerhof–Beemer–Cormane",
    # Whipple's disease – George Hoyt Whipple
    "Whipple",
    # Williams syndrome – J. C. P. Williams [typo fixed in Wikipedia]
    "Williams",
    # Wilms' tumor – Max Wilms
    "Wilms",
    # Wilson's disease – Samuel Alexander Kinnier Wilson
    "Wilson",
    # Willis–Ekbom syndrome – Thomas Willis, Karl-Axel Ekbom
    "Willis–Ekbom",
    # Wiskott–Aldrich syndrome – Alfred Wiskott, Robert Aldrich
    "Wiskott–Aldrich",
    # Wittmaack–Ekbom syndrome – Theodur Wittmaack, Karl-Axel Ekbom
    "Wittmaack–Ekbom",
    # Wohlfart–Kugelberg–Welander disease – Karl Gunnar Vilhelm Wohlfart, Erik Klas Henrik Kugelberg, Lisa Welander
    "Wohlfart–Kugelberg–Welander",
    # Wolff–Parkinson–White syndrome – Louis Wolff, John Parkinson, Paul Dudley White
    "Wolff–Parkinson–White",
    # Wolman disease – Moshe Wolman
    "Wolman",

    # -------------------------------------------------------------------------
    # Y
    # -------------------------------------------------------------------------
    # Yesudian syndrome – Paul Yesudian
    "Yesudian",

    # -------------------------------------------------------------------------
    # Z
    # -------------------------------------------------------------------------
    # Zahorsky syndrome I – John Zahorsky (a.k.a. John Von Zahorsky)
    "Zahorsky",
    # Zahorsky syndrome II (a.k.a. Mikulicz' Aphthae, Mikulicz' Disease, Sutton disease 2, Von Mikulicz' Aphthae, Von Zahorsky disease) – John Zahorsky (a.k.a. John Von Zahorsky)
    "Zahorsky",
    # Zellweger syndrome – Hans Ulrich Zellweger
    "Zellweger",
    # Zenker diverticulum – Friedrich Albert von Zenker
    "Zenker",
    # Zenker paralysis – Friedrich Albert von Zenker
    "Zenker",
    # Zieve syndrome – Leslie Zieve
    "Zieve",
    # Zimmermann–Laband syndrome (a.k.a. Laband syndrome, Laband–Zimmermann syndrome) – Karl Wilhelm Zimmermann
    "Zimmermann–Laband",
    # Zollinger–Ellison syndrome – Robert Zollinger, Edwin Ellison
    "Zollinger–Ellison",
    # Zondek–Bromberg–Rozin syndrome (a.k.a. Zondek syndrome) – Bernhard Zondek, Yehuda M. Bromberg, R.Rozin
    "Zondek–Bromberg–Rozin",
    # Zuelzer syndrome – Wolf William Zuelzer
    "Zuelzer",
    # Zuelzer–Kaplan syndrome II (a.k.a. Crosby syndrome) – Wolf William Zuelzer, E. Kaplan
    "Zuelzer–Kaplan",
    # Zuelzer–Ogden syndrome – Wolf William Zuelzer, Frank Nevin Ogden
    "Zuelzer–Ogden",
    # Zumbusch psoriasis – Leo Ritter von Zumbusch
    "Zumbusch",
    # Zumbusch syndrome (a.k.a. Csillag disease, Csillag syndrome, Hallopeau disease, von Zumbusch syndrome) – Leo Ritter von Zumbusch
    "Zumbusch",

]


for _composite in SIMPLE_EPONYM_LIST:
    _add_eponym(_composite)
