# vim: set fileencoding=utf-8 :
#! /usr/bin/env python3

import pathlib
import os
import collections
import multiprocessing
import argparse

import pandas as pd

import xsdir
import ace

class DataDirectory:
    def __init__(self, XSDIR, datapath):
        self.XSDIR = XSDIR
        self.datapath = datapath

        self.metadataFunctions = {
            'c': self._fastNeutron,
            'nc': self._fastNeutron
        }


    def _fastNeutron(self, index):
        """
        Add metadata from all fast neutron ACE files.

        index: Location in self.XSDIR of row where we are adding metadata
        """
        path = pathlib.Path(self.datapath, self.XSDIR.loc[index].path)
        print(path)

        address = self.XSDIR.loc[index].address
        ACE = ace.ace(filename=path, headerOnly=False, start_line=address)

        meta = {}
        self.XSDIR.loc[index, 'length'] = int(ACE.NXS[1])
        NE = int(ACE.NXS[3])
        self.XSDIR.loc[index, 'NE'] = NE
        self.XSDIR.loc[index, 'Emax'] = round(ACE.XSS[NE], 1)
        if (ACE.JXS[12] != 0) or (ACE.JXS[13] != 0):
            self.XSDIR.loc[index, 'GPD'] = True
        else:
            self.XSDIR.loc[index, 'GPD'] = False

        if ACE.JXS[2] != 0:
            if ACE._XSS[(ACE.JXS[2] - 1)] > 0:
                self.XSDIR.loc[index, 'nubar'] = 'nubar'
            else:
                self.XSDIR.loc[index, 'nubar'] = 'both'
        else:
            self.XSDIR.loc[index, 'nubar'] = 'no'

        # Charged particle  see XTM:96-200
        if ACE.NXS[7] > 0:
            self.XSDIR.loc[index, 'CP'] = True
        else:
            self.XSDIR.loc[index, 'CP'] = False
        # Delayed neutron
        if ACE.JXS[24] > 0:
            self.XSDIR.loc[index, 'DN'] = True
        else:
            self.XSDIR.loc[index, 'DN'] = False
        # Unresolvedresonance
        if ACE.JXS[23] > 0:
            self.XSDIR.loc[index, 'UR'] = True
        else:
            self.XSDIR.loc[index, 'UR'] = False

    def _default(self, index):
        """
        _default does nothing, but prevents Python from crashing when 
        """
        pass


    def extend(self, index):
        """
        extend will add metadata to a row of self.XSDIR given the row's index
        """
        lib_type = self.XSDIR.loc[index].lib_type

        self.metadataFunctions.get(lib_type, self._default)(index)

def getXSDIR(datapath):
    """
    getXSDIR will extract the XSDIR data and save it in a pandas.DataFrame. It
    also adds some additional columns for metadata. It returns the XSDIR.
    """

    AWRs, XSDIR = xsdir.readXSDIR(datapath)

    # Additional columns for metadata
    metaColumns = {
        # FastNeutron
        'NE': int,
        'length': int,
        'Emax': float,
        'GPD': bool,
        'nubar': str,
        'CP': bool,
        'DN': bool,
        'UR': bool,
        # Thermal Scattering
    }

    # Add columns to DataFrame for metadata
    for name, dtype in metaColumns.items():
        if name not in XSDIR.columns:
            XSDIR[name] = pd.Series(dtype=dtype)
    return XSDIR

def processInput():
    description= "Preparing to list available ACE data"
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--xsdir', type=pathlib.Path, 
        default = pathlib.Path(os.environ['DATAPATH'], 'xsdir'),
        help="Path to xsdir file. Defaults to $DATAPATH/xsdir")

    parser.add_argument('-N', type=int,
        default=multiprocessing.cpu_count()-1,
        help="Number of parallel threads.")


    return parser.parse_args()


if __name__ == "__main__":

    args = processInput()
    XSDIR = getXSDIR(args.xsdir)
    XSDIR = XSDIR.query('ZA == 1001')

    ddir = DataDirectory(XSDIR, args.xsdir.parent)

    with multiprocessing.Pool(args.N) as pool:
        pool.map(ddir.extend, XSDIR.index)

    with open('xsdir.json', 'w') as jsonFile:
        json = XSDIR.to_json(orient='records', default_handler=str, indent=2)
        jsonFile.write(json)
