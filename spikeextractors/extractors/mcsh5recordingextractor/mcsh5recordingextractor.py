from spikeextractors import RecordingExtractor

import numpy as np
#import ctypes

try:
    import h5py
    HAVE_MCSH5 = True
except ImportError:
    HAVE_MCSH5 = False

class MCSH5RecordingExtractor(RecordingExtractor):

    extractor_name = 'MCSH5RecordingExtractor'
    has_default_locations = False
    installed = HAVE_MCSH5  # check at class level if installed or not
    is_writable = False
    mode = 'file'
    _gui_params = [
        {'name': 'file_path', 'type': 'file', 'title': "Path to file (.h5 or .hdf5)"},
    ]
    installation_mesg = "To use the MCSH5RecordingExtractor install h5py: \n\n pip install h5py\n\n"  # error message when not installed

    def __init__(self, file_path, verbose=False):
        assert HAVE_MCSH5, "To use the MCSH5RecordingExtractor install h5py: \n\n pip install h5py\n\n"
        self._recording_file = file_path
        self._rf, self._nFrames, self._samplingRate, self._nRecCh, \
        self._channel_ids, self._electrodeLabels, self._exponent, self._convFact \
        = openMCSH5File(
            self._recording_file, verbose)
        RecordingExtractor.__init__(self)
        
    def __del__(self):
        self._rf.close()

    def get_channel_ids(self):
        return self._channel_ids
    
    def get_num_frames(self):
        return self._nFrames

    def get_sampling_frequency(self):
        return self._samplingRate

    def get_traces(self, channel_ids=None, start_frame=None, end_frame=None):
        if start_frame is None:
            start_frame = 0
        if end_frame is None:
            end_frame = self.get_num_frames()
        if channel_ids is None:
            channel_ids = self._channel_ids
        else:
            if type(channel_ids) is int:
                assert channel_ids in self._channel_ids, 'channel_id {} not found'.format(channel_ids)
                channel_indices = np.where(self._channel_ids==channel_ids)[0][0]
            else:
                channel_indices = []
                for m in channel_ids:
                    assert m in self._channel_ids, 'channel_id {} not found'.format(m)
                    channel_indices.append(np.where(self._channel_ids==m)[0][0])
                
        stream = self._rf.require_group('/Data/Recording_0/AnalogStream/Stream_0')
        data_V = np.array(stream.get('ChannelData'),dtype=np.int)*self._convFact.astype(float)*(10.0**(self._exponent))

        return data_V[channel_indices, start_frame:end_frame]

    @staticmethod
    def write_recording(recording, save_path):
        # Not implemented
        # An informative example is in BiocamRecordingExtractor

        assert HAVE_MCSH5, "To use the MCSH5RecordingExtractor install h5py: \n\n pip install h5py\n\n"
        raise NotImplementedError


def openMCSH5File(filename, verbose=False):
    """Open an MCS hdf5 file, read and return the recording info."""
    rf = h5py.File(filename, 'r')
    
    stream = rf.require_group('/Data/Recording_0/AnalogStream/Stream_0')
    data = np.array(stream.get('ChannelData'),dtype=np.int)
    timestamps = np.array(stream.get('ChannelDataTimeStamps'))
    info = np.array(stream.get('InfoChannel'))
    
    Unit = info['Unit'][0]
    Tick = info['Tick'][0]/1e6
    exponent = info['Exponent'][0]
    convFact = info['ConversionFactor'][0]
    
    nRecCh, nFrames = data.shape
    channel_ids = info['ChannelID']
    assert len(np.unique(channel_ids)) == len(channel_ids), 'Duplicate MCS channel IDs found'
    electrodeLabels = info['Label']
    
    TimeVals = np.arange(timestamps[0][0],timestamps[0][2]+1,1)*Tick
    
    assert Unit==b'V', 'Unexpected units found, expected volts, found {}'.format(Unit.decode('UTF-8'))
    data_V = data*convFact.astype(float)*(10.0**(exponent))
    
    timestep_avg = np.mean(TimeVals[1:]-TimeVals[0:-1])
    timestep_std = np.std(TimeVals[1:]-TimeVals[0:-1])
    timestep_min = np.min(TimeVals[1:]-TimeVals[0:-1])
    timestep_max = np.min(TimeVals[1:]-TimeVals[0:-1])
    assert all(np.abs(np.array((timestep_min, timestep_max))-timestep_avg)/timestep_avg < 1e-6), 'Time steps vary by more than 1 ppm'
    samplingRate = 1./timestep_avg

    if verbose:
        print('# MCS H5 data format')
        print('#')
        print('# File: {}'.format(rf.filename))
        print('# File size: {:.2f} MB'.format(rf.id.get_filesize()/1024**2))
        print('#')
        for key in rf.attrs.keys():
            print('# {}: {}'.format(key,rf.attrs[key]))
        print('#')
        print('# Signal range: {:.2f} to {:.2f} µV'.format(np.amin(data_V)*1e6,np.amax(data_V)*1e6))
        print('# Number of channels: {}'.format(nRecCh))
        print('# Number of frames: {}'.format(nFrames))
        print('# Time step: {:.2f} µs ± {:.5f} % (range {} to {})'.format(timestep_avg*1e6, timestep_std/timestep_avg*100, timestep_min*1e6, timestep_max*1e6))
        print('# Sampling rate: {:.2f} Hz'.format(samplingRate))
        print('#')
        print('# MCSH5RecordingExtractor currently only reads /Data/Recording_0/AnalogStream/Stream_0')

    return (rf, nFrames, samplingRate, nRecCh, channel_ids, electrodeLabels, exponent, convFact)
