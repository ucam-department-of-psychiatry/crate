from typing import Optional

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.all_processors import make_processor

from crate_anon.nlp_web.constants import PROCESSORS


class Processor(object):
    """
    Class for containing information about processors.

    For ease of finding processor info based on name and version
    (alternative would be a dictionary in which the keys were name_version
    and the values were another dictionary with the rest of the info)
    """
    # Master list of all instances (processors)
    processors = {}

    def __init__(self,
                 name: str,
                 title: str,
                 version: str,
                 is_default_version: bool,
                 description: str,
                 proctype: Optional[str] = None) -> None:
        self.name = name
        self.title = title
        self.version = version
        self.is_default_version = is_default_version
        self.description = description
        self.processor_id = "{}_{}".format(self.name, self.version)

        self.parser = None  # type: BaseNlpParser
        if not proctype:
            self.proctype = name
        else:
            self.proctype = proctype
        self.dict = {
            'name': name,
            'title': title,
            'version': version,
            'is_default_version': is_default_version,
            'description': description,
        }

        # Add instance to list of processors
        Processor.processors[self.processor_id] = self

    def set_parser(self) -> BaseNlpParser:
        """
        Sets 'self.parser' to an instance of a subclass of 'BaseNlpParser'
        not bound to any nlpdef or cfgsection, unless self.proctype is GATE.'
        """
        if self.proctype != "GATE":
            self.parser = make_processor(processor_type=self.proctype,
                                         nlpdef=None, section=None)
        # else: do nothing


for proc in PROCESSORS:
    Processor(
        name=proc['name'],
        title=proc['title'],
        version=proc['version'],
        is_default_version=proc['is_default_version'],
        description=proc['description'],
        proctype=proc.get('proctype')
    )





