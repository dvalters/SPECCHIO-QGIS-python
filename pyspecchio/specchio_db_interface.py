#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 26 09:54:34 2018

@author: Declan Valters
"""
import os
import sys

import jpype as jp
import numpy as np
import pandas as pd

import spectra_parser as specp
import ancildata_parser as ancilparser


def init_jvm(jvmpath=None):
    """
    Checks first to see if JVM is already running.
    """
    if jp.isJVMStarted():
        return
    try:
        client_java_path = os.environ['SPECCHIO_JAVA_CLIENT']
        client_java_argument = "-Djava.class.path=" + client_java_path
        jp.startJVM(jp.getDefaultJVMPath(), "-ea", client_java_argument)
    except Exception as exc:
        print(exc)
        sys.exit(1)

init_jvm()

spclient = jp.JPackage('ch').specchio.client
spquery = jp.JPackage('ch').specchio.queries
sptypes = jp.JPackage('ch').specchio.types
spgui = jp.JPackage('ch').specchio.gui
spreader_campaign = jp.JPackage('ch').specchio.file.reader.campaign

# TODO: Call or attribute? Check API here...
metaparam = sptypes.MetaParameter


class SpecchioClient(object):
    """Specchio db client in Python object form"""
    pass


class Campaign(object):
    """Object for storing an instance of a campaign"""
    def __init__(self, campaign_name):
        pass


class specchioDBinterface(object):
    """Object to manage interations with the SPECCHIO db and handle uplodas
    from pandas dataframes"""

    PICO_METADATA = [
        'Batch', 'Dark', 'Datetime', 'Direction',
        'IntegrationTime', 'IntegrationTimeUnits',
        'NonlinearityCorrectionCoefficients', 'OpticalPixelRange',
        'Run', 'SaturationLevel', 'SerialNumber',
        'TemperatureDetectorActual', 'TemperatureDetectorSet',
        'TemperatureHeatsink', 'TemperatureMicrocontroller',
        'TemperaturePCB', 'TemperatureUnits', 'Type',
        'WavelengthCalibrationCoefficients', 'name']

    # Pico metadata name key to database descriptor name
    MAP_PICO_METADATA_SPECCHIONAME = {
        'Batch': 'Batch',
        'Dark': 'Dark',   # Automatic Dark Correction? (boolean)
        'Datetime': 'Datetime',
        'Direction': 'Direction',
        'IntegrationTime': 'Integration Time',
        'IntegrationTimeUnits': 'Integration Time Units',
        'NonlinearityCorrectionCoefficients':
            'Nonlinearity Correction Coefficients',
        'OpticalPixelRange': 'Optical Pixel Range',
        'Run': 'Run',
        'SaturationLevel': 'Saturation Level',
        'SerialNumber': 'Instrument Serial Number',
        'TemperatureDetectorActual': 'Temperature Detector Actual',
        'TemperatureDetectorSet': 'Temperature Detector Set',
        'TemperatureHeatsink': 'Temperature Detector Heatsink',
        'TemperatureMicrocontroller': 'Temperature Detector Microcontroller',
        'TemperaturePCB': 'Temperature Detector PCB',
        'TemperatureUnits': 'Temperature Units',
        'Type': 'Type',
        'WavelengthCalibrationCoefficients':
            'Wavelength Calibration Coefficients',
        'name': 'name'}

    # Other metadata -should contain sublevel headings or No?
    # 'Vegetation Biophysical Parameters'
    MAP_ANCIL_METADATA_SPECCHIONAME = {
        'Fluorescence': '',  # Tricky to see how this will fit into SPECCHIO DB
        'GS':               ('Fertiliser_level', 'GS'),
        # Harvest folder:
        # =-=-=-=-=-=-=-=
        'Harvest':  ('Fertiliser_level', 'Yield_TonnesPerHectare',
                     'TGW', 'FreshWeightKg', 'DryMatter%', 'no_in15g'),
        'CN':       ('Fertiliser_level', 'N%', 'C%'),
        'HI':       ('Fertiliser_level', 'StrawFreshWeight',
                     'StrawDryWeight', 'WholeEarWeight',
                     'GrainWeight', 'ChaffWeight', 'HI'),
        # =-=-=-=-=-=-=-=
        'Height':       ('Fertiliser_level', 'Height1', 'Height2', 'Height3',
                         'Height4', 'Height5', 'Plot_height'),
        'LAI': '',  # Almost a database in itself...?
        'SPAD':         ('Fertiliser_level', 'SPAD1', 'SPAD2', 'SPAD3',
                         'SPAD4', 'SPAD5', 'SPAD6', 'SPAD7',
                         'SPAD8', 'SPAD9', 'SPAD10', 'Plot_Average'),
        'ThetaProbe':   ('Fertiliser_level', 'Moisture1', 'Moisture2',
                         'Moisture3', 'Moisture4', 'Moisture5',
                         'Plot Moisture'),
        # Soils Folder
        'NitrateAmmonia': ('Fertiliser_level', 'NO2NO3mgperlN',
                           'AmmoniamgperlN'),
        'ResinExtracts':  ('Fertiliser_level', 'Ammonia_set1', 'Nitrate_set1'),
        'Moisture':       ('Fertiliser_level', 'Moisture%g/g'),
        'pH':             ('Fertiliser_level', 'pH')}

    def __init__(self, campaign_name):
        """
        Check JVM is up and running, set up a database client and connect
        to the server.
        """
        init_jvm()
        self.campaign_name = campaign_name
        client_factory = spclient.SPECCHIOClientFactory.getInstance()
        descriptor_list = client_factory.getAllServerDescriptors()
        self.specchio_client = client_factory.createClient(
            descriptor_list.get(0))

        # Set the campaign name and ID
        self.campaign = sptypes.SpecchioCampaign()
        self.campaign.setName(self.campaign_name)
        self.c_id = self.specchio_client.insertCampaign(self.campaign)
        # Store the campaign ID in the campaign object
        self.campaign.setId(self.c_id)
        self.subhierarchy = "PlotData"

    @classmethod
    def read_metadata(cls, filename):
        """ Reads the example metadata csv file and returns a pandas dataframe
        Read in the csv, transposing it because the names are actually
        in the 1st column.
        """
        df = pd.read_csv(filename, header=None).transpose()
        # Now use the transposed 1st row to create the column names
        df.columns = df.iloc[0]
        # Now we can drop row 1 as it is loaded as column names
        df = df.reindex(df.index.drop(0))
        return df

    def set_spectra_file_info(
            self, spspectra_file, spectra_filepath, spectra_filename):
        """Set basic info about the spectra file being processed"""
        # What happens if is dataframe?
        spspectra_file.setPath(spectra_filepath)
        spspectra_file.setFilename(spectra_filename)
        spspectra_file.setCompany('UoE')
        # Creating a metadata hierarchy
        hierarchy_id = self.specchio_client.getSubHierarchyId(
            self.campaign, self.subhierarchy, 0)
        # 0 argument specifices the hierarchy has no parent.
        # Set the campaign and hierarchy to store in
        spspectra_file.setHierarchyId(hierarchy_id)
        spspectra_file.setCampaignId(self.c_id)

    def read_test_data(self, filename, filepath):
        """Opens and read the test csv spectra and metadata files into a
        numpy array"""
        with open(filepath + filename, 'r') as csvfile:
            wavelens_and_spectra = np.loadtxt(csvfile, delimiter=',')
            wavelengths = wavelens_and_spectra[:, 0]
            spectra = wavelens_and_spectra[:, 1:]

            # Now get the metadata
            metadata = self.read_metadata(filepath + "metadata.csv")
            return wavelengths, spectra, metadata

    def get_dummy_spectra_file(self):
        """Produce some dummy spectra for when uploading metadata only
        dummy_spectra = None
        with open(dummy_spectra) as df:
            pass
        """
        raise NotImplementedError

    def get_test_spectra(self):
        """Get spectra from the test file spectra.csv"""
        pass

    @classmethod
    def get_all_pico_metadata(cls, spectrafile):
        """ Gets all the metadata from the PICO JSON spectra files.

        Returns:
            A list of metadata dictionaries, four for each of the four spectra
        """
        return [spectrafile.get_spectra_metadata(x) for x in range(0, 4)]

    @classmethod
    def get_all_pico_spectra(cls, spectrafile):
        """Gets a spectra from the PICO json spectra files.

        Returns an array of lists, because lists are not same lengths
        (Not a 2D array, as might be expected)
        """
        return np.array(
            [spectrafile.get_spectra_pixels(x) for x in range(0, 4)])

    @classmethod
    def get_all_ancil_metadata(cls, ancildatadir):
        """
        Gets all the dataframes from the ancillary data.
        """
        return ancilparser.extract_dataframes(ancildatadir)

    def map_pico_spectrafile_to_plotID(self):
        """Gets the PlotID from the pico file...somehow"""
        pass

    @classmethod
    def get_single_pico_spectra(cls, spectra_num):
        """Gets a spectra from the PICO json spectra files"""
        return specp.get_spectra_pixels(spectra_num)

    def retrieve_metadata_from_hash(self, metadata_key):
        mp = metaparam.newInstance(
                self.specchio_client.getAttributesNameHash().get(
                        self.MAP_PICO_METADATA_SPECCHIONAME[metadata_key]))
        return mp

    def add_pico_metadata_for_spectra(self, smd, metadata, spectra_index):
        """Adds the spectrometer-specific metadata to the spectra file

        Todo:
            Deal better with null pointer exception.
            How to handle 'null' unquoted value in pico data
            Conversion of lists to comma separated string.
            Add plot number metadata.
        """
        for metadata_key in self.PICO_METADATA:

            try:
                mp = self.retrieve_metadata_from_hash(metadata_key)
                mp.setValue(metadata[spectra_index][metadata_key])
                smd.addEntry(mp)
            except KeyError as ke:
                print("Warning: key: ", ke,
                      " is not in metadata for this spectra.")
            except RuntimeError:  # Usually a java type conversion error
                try:
                    mp = self.retrieve_metadata_from_hash(metadata_key)
                    mp.setValue(str(metadata[spectra_index][metadata_key]))
                    smd.addEntry(mp)
                except Exception as ex:
                    print("Attempt at string conversion raised"
                          "further excpetion: ", ex)
            except jp.JavaException as je:
                # Usually a java null pointer exception
                print("Warning:", je,
                      self.MAP_PICO_METADATA_SPECCHIONAME[metadata_key])

    def add_ancillary_metadata_for_spectra(
             self, smd, ancil_metadata, spectra_index):
        """Adds the 'other' anciliary metadata, e.g. LAI, Soils etc to the
        spectra file metadata. Most of this is not really specific metadata
        to the instrument, but other measured data.

        This metadata comes from the parser_pandas module file, which parses
        the excel files and returns them as pandas dataframes, by data type,
        with the rows in each dataframe referring to the plot.

        """
        for ancildata_key in self.MAP_ANCIL_METADATA_SPECCHIONAME.keys():
            mp = metaparam.newInstance(
                    self.specchio_client.getAttributesNameHash().get(
                        self.MAP_ANCIL_METADATA_SPECCHIONAME[ancildata_key]))
            mp.setValue(ancil_metadata[spectra_index][ancildata_key])
            smd.addEntry(mp)

    def add_ancillary_metadata_for_dummyspectra(self, smd):
        """You are in a row of the ancil metdata dataframe and you want to add
        everything on this row to metadata"""
        pass

    def specchio_upload_ancil_with_dummy_spectra(self, ancildir):
        """Uploads ancillary metadata without spectra files.

        Creates a dummy spectra file at the plot level.
        Plot level name can be taken from the dataframe rows...

        Attach metadata in subsequent columns to this dummy spectra.

        Upload to DB.

        Args:
          ancildir: top-level directory containing the data.

        Logic:
          Dummy pico file created from plot name (and date?)
          but plot name is in the pandas dataframe from each ancil.
          So, loop through each dataframe, pop off the date and append it to
          the first row plot name - this is your dummy spectra name for the
          dummy pico file to write out.

          Now create the usual spectra file object data

          Upload the metdata **to this dummy file** in the ususal way.


          Check given date for new files...
          Check file modification time. etc..

        """
        ancil_data = self.get_all_ancil_metadata(ancildir)
        plot_ids = set()
        pico_dir = "./picotest/"

        for df in ancil_data:
            if 'LAI' in df:  # Odd format from PRN files
                break
            category = ancilparser.get_category_from_df_key(df)
            datestr = ancilparser.get_date_from_df_key(df)

            # Loop through the rows in each dataframe
            for _, row in ancil_data[df].iterrows():
                # We need to create a unique name for each dummy spectra
                plot_id_name = row[0] + '_' + datestr
                plot_ids.add(plot_id_name)
                dummy_pico_name = plot_id_name + ".pico"
                # Don't create new dummy files if ones already exist!
                if not os.path.exists(pico_dir + dummy_pico_name):
                    # Write a new dummy pico file
                    specp.DummySpectraFile.generate_dummy_spectra_for_ancil(
                            pico_dir, dummy_pico_name)
                # Now do all the spectra file object stuff
                # This is for the Java class...
                dummy_spectrafile_obj = sptypes.SpectralFile()
                # And this one for the Python object
                dummy_spectrafile = specp.DummySpectraFile(
                    dummy_pico_name, os.path.abspath(pico_dir))
                self.set_spectra_file_info(dummy_spectrafile_obj,
                                           dummy_spectrafile.dummyfile,
                                           dummy_spectrafile.dummspecpath)
                smd = sptypes.Metadata()
                dummy_spectrafile_obj.addSpectrumFilename(dummy_pico_name)

                category = ancilparser.get_category_from_df_key(df)
                subcateogries = self.MAP_ANCIL_METADATA_SPECCHIONAME[category]

                for subcategory in subcateogries:
                    value = row[subcategory]
                    # Now each column header is a metadata key. It must be added
                    # to each spectra file. PlotID + date.

                    # Pop off the value from the row by indexing using the
                    # subcategory in the class dictionary.
                    mp = metaparam.newInstance(
                        self.specchio_client.getAttributesNameHash().get(
                            subcategory))
                    mp.setValue(value)
                    smd.addEntry(mp)
                # check we are not overwriting spectra files somehow

    def specchio_upload_pico_spectra(self, spectrafile):
        """Upload the PICO type spectra.

        Args:
            spectrafile: a SpectraFile object

        Remember, the specs are:
            2 sets of Up and Down spectra (four in total)
            Each have their own set of metadata
        """
        # Create a spectra file object
        spspectra_file_obj = sptypes.SpectralFile()
        self.set_spectra_file_info(spspectra_file_obj,
                                   spectrafile.sfile, spectrafile.spath)
        # as below.... loop through the four spectra
        spectra = self.get_all_pico_spectra(spectrafile)
        metadata = self.get_all_pico_metadata(spectrafile)
        # Should be 4 for PICO file format
        num_spectras = np.size(spectra)  ## odd errors for the other sample PICO? (non USB, s2 one)
        print(num_spectras)
        # TODO: remove hard coding
        num_wavelens = 2048
        # Should not be hard coded in final version, OK for now...
        dummy_wavelens = np.linspace(1.0, 2048.0, num_wavelens)
        # Could be max len of spectra lists? 1044 vs 2044
        spspectra_file_obj.setNumberOfSpectra(num_spectras)
        # A numpy temporary holding array, dims of no of spectra x no of wvls
        spectra_array = np.zeros((num_spectras, num_wavelens))

        for i in range(0, num_spectras):
            vector = spectra[i]  # 4 spectras from the PICO
            # TODO: not sure what the wavelengths are yet...use length 1...n
            for w in range(0, len(vector)):
                spectra_array[i, w] = vector[w] 
            # Add wavelens
            spspectra_file_obj.addWvls(
                [jp.java.lang.Float(x) for x in dummy_wavelens])
            # Add filename:
            # we add an automatic number here to make them distinct
            fname_spectra = spectrafile.sfile + str(i)
            spspectra_file_obj.addSpectrumFilename(fname_spectra)

            # Metadata...FOR EACH SPECTRA (use dummy if needed)
            # =-=-=-=-=-=
            smd = sptypes.Metadata()
            self.add_pico_metadata_for_spectra(smd, metadata, i)
            # self.add_ancillary_metadata_for_spectra(smd, metadata, i)
            spspectra_file_obj.addEavMetadata(smd)

        # Convert the spectra list to a suitable
        javafloat_spectra_list = [
            [jp.java.lang.Float(j) for j in i] for i in spectra_array]

        spspectra_file_obj.setMeasurements(javafloat_spectra_list)

        self.specchio_client.insertSpectralFile(spspectra_file_obj)

    def specchio_uploader_test(self, filename, filepath,
                               subhierarchy, use_dummy_spectra=False):
        """Uploader for the test data.

        DEPRECATED

        The following code takes the spectral file object and fills
        the spectral data into a Java array and the Metadata into a metadata
        object. The spectral file object is then stored in the database under
        the campaign and hierarchy we created.

        This code is specific to the spectra file/data being uploaded
        it should be made more general purpose"""
        # Create a spectra file object and set its params
        spspectra_file = sptypes.SpectralFile()
        self.set_spectra_file_info(spspectra_file, filepath, filename)

        # read test data
        wavelengths, spectra, metadata = self.read_test_data(
            filename, filepath)

        # Now we can set the number of spectra
        spspectra_file.setNumberOfSpectra(np.size(spectra, 1))

        # A numpy temporary holding array, dims of no of spectra x no of wvls
        spectra_array = np.zeros((np.size(spectra, 1), len(wavelengths)))

        for i in range(0, np.size(spectra, 1)):
            vector = spectra[:, i]
            for w in range(0, len(wavelengths)):
                # Perhaps create a numpy array first and then populate?
                spectra_array[i, w] = vector[w]

            spspectra_file.addWvls(
                [jp.java.lang.Float(x) for x in wavelengths])

            # Add filename:
            # we add an automatic number here to make them distinct
            fname_spectra = filename + str(i)
            spspectra_file.addSpectrumFilename(fname_spectra)

            # Metadata has to be added at the spectra level,
            # i.e. metadata for each spectra
            smd = sptypes.Metadata()
            # We add metadata for every spectra
            if i > 0:
                # Add plot number metaparameter
                mp = metaparam.newInstance(
                    self.specchio_client.getAttributesNameHash().get(
                        'Target ID'))
                mp.setValue(str(metadata['Plot'][i]))
                smd.addEntry(mp)

                # Add Nitrate metaparameter
                mp = metaparam.newInstance(
                    self.specchio_client.getAttributesNameHash().get(
                        'Nitrate Nitrogen'))
                mp.setValue(metadata['Nitrate Nitrogen Mg/Kg'][i])
                smd.addEntry(mp)

                # Add Phosphorous metaparameter
                mp = metaparam.newInstance(
                    self.specchio_client.getAttributesNameHash().get(
                        'Phosphorus'))
                mp.setValue(metadata['Phosphorus %'][i])
                smd.addEntry(mp)

                spspectra_file.addEavMetadata(smd)

        javafloat_spectra_list = [
            [jp.java.lang.Float(j) for j in i] for i in spectra_array]

        spspectra_file.setMeasurements(javafloat_spectra_list)

        self.specchio_client.insertSpectralFile(spspectra_file)
