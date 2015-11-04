#!/usr/bin/env python3
# consent/utils.py


def pdf_template_dict(patient=True):
    if patient:
        fontsize = "12pt"
        lineheight = "14pt"
    else:
        fontsize = "10pt"
        lineheight = "12pt"
    # NHS Blue is rgb(0, 114, 198); see
    # http://www.nhsidentity.nhs.uk/page/11951/tools-and-resources/
    #        nhs-brand-basics/nhs-colours/nhs-colours
    return {
        'fontsize': fontsize,
        'lineheight': lineheight,
    }
