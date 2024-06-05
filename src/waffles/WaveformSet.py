import math
import inspect
from typing import Tuple, List, Callable, Optional

import uproot
import numpy as np
from plotly import graph_objects as pgo
from plotly import subplots as psu

from src.waffles.NWaveform import Waveform
from src.waffles.WaveformAdcs import WaveformAdcs
from src.waffles.WfAna import WfAna
from src.waffles.WfAnaResult import WfAnaResult
from src.waffles.Exceptions import generate_exception_message

class WaveformSet:

    """
    This class implements a set of waveforms.

    Attributes
    ----------
    Waveforms : list of Waveform objects
        Waveforms[i] gives the i-th waveform in the set.
    PointsPerWf : int
        Number of entries for the Adcs attribute of
        each Waveform object in this WaveformSet object.
    Runs : set of int
        It contains the run number of any run for which
        there is at least one waveform in the set.
    AvailableChannels : dictionary
        It is a dictionary whose keys are endpoints (int) 
        and its values are sets of channels (set of int).
        If there is at least one Waveform object within
        this WaveformSet which comes from endpoint n, then
        n belongs to AvailableChannels.keys(). 
        AvailableChannels[n] is a set of channels for 
        endpoint n. If there is at least one waveform for
        endpoint n and channel m, then m belongs to 
        AvailableChannels[n].
    MeanAdcs : WaveformAdcs
        The mean of the adcs arrays for every waveform
        or a subset of waveforms in this WaveformSet. It 
        is a WaveformAdcs object whose TimeStep_ns
        attribute is assumed to match that of the first
        waveform which was used in the average sum.
        Its Adcs attribute contains PointsPerWf entries,
        so that MeanAdcs.Adcs[i] is the mean of 
        self.Waveforms[j].Adcs[i] for every value
        of j or a subset of values of j, within 
        [0, len(self.__waveforms) - 1]. It is not 
        computed by default. I.e. if self.MeanAdcs 
        equals to None, it should be interpreted as 
        unavailable data. Call the 'compute_mean_waveform' 
        method of this WaveformSet to compute it.
    MeanAdcsIdcs : tuple of int
        It is a tuple of integers which contains the indices
        of the waveforms, with respect to this WaveformSet,
        which were used to compute the MeanAdcs.Adcs 
        attribute. By default, it is None. I.e. if 
        self.MeanAdcsIdcs equals to None, it should be 
        interpreted as unavailable data. Call the 
        'compute_mean_waveform' method of this WaveformSet 
        to compute it.

    Methods
    ----------
    ## Add the list of methods and a summary for each one here
    """

    def __init__(self,  *waveforms):
        
        """
        WaveformSet class initializer
        
        Parameters
        ----------
        waveforms : unpacked list of Waveform objects
            The waveforms that will be added to the set
        """

        ## Shall we add type checks here?
        
        self.__waveforms = list(waveforms)

        if not self.check_length_homogeneity():
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.__init__()',
                                                        'The length of the given waveforms is not homogeneous.'))
        
        self.__points_per_wf = len(self.__waveforms[0].Adcs)

        self.__runs = set()
        self.update_runs()

        self.__available_channels = {}
        self.update_available_channels()    # Running on an Apple M2, it took 
                                            # ~ 52 ms to run this line for a
                                            # WaveformSet with 1046223 waveforms
        self.__mean_adcs = None
        self.__mean_adcs_idcs = None

    #Getters
    @property
    def Waveforms(self):
        return self.__waveforms
    
    @property
    def PointsPerWf(self):
        return self.__points_per_wf
    
    @property
    def Runs(self):
        return self.__runs
    
    @property
    def AvailableChannels(self):
        return self.__available_channels
    
    @property
    def MeanAdcs(self):
        return self.__mean_adcs
    
    @property
    def MeanAdcsIdcs(self):
        return self.__mean_adcs_idcs
    
    def check_length_homogeneity(self) -> bool:
            
            """
            This method returns True if the Adcs attribute
            of every Waveform object in this WaveformSet
            has the same length. It returns False if else.

            Returns
            ----------
            bool
            """

            length = len(self.__waveforms[0].Adcs)
            for i in range(1, len(self.__waveforms)):
                if len(self.__waveforms[i].Adcs) != length:
                    return False
            return True
    
    def update_runs(self) -> None:
        
        """
        This method iterates through the whole WaveformSet
        and updates the self.__runs attribute of this object. 

        Returns
        ----------
        None
        """

        for wf in self.__waveforms:
            self.__runs.add(wf.RunNumber)
        return
    
    def update_available_channels(self) -> None:
        
        """
        This method iterates through the whole WaveformSet
        and updates the self.__available_channels attribute of 
        this object. 

        Returns
        ----------
        None
        """

        for wf in self.__waveforms:
            try:
                self.__available_channels[wf.Endpoint].add(wf.Channel)
            except KeyError:
                self.__available_channels[wf.Endpoint] = set()
                self.__available_channels[wf.Endpoint].add(wf.Channel)
        return
    
    def analyse(self,   label : str,
                        analyser_name : str,
                        baseline_limits : List[int],
                        *args,
                        int_ll : int = 0,
                        int_ul : Optional[int] = None,
                        overwrite : bool = False,
                        **kwargs) -> dict:
        
        """
        For each Waveform in this WaveformSet, this method
        calls its 'analyse' method passing to it the parameters
        given to this method. In turn, Waveform.analyse()
        (actually WaveformAdcs.analyse()) creates a WfAna
        object and adds it to the Analyses attribute of the 
        analysed waveform. It also runs the indicated analyser 
        method (up to the 'analyser_name' parameter) on the 
        waveform, and adds its results to the 'Result' and 
        'Passed' attributes of the newly created WfAna object. 
        Also, it returns a dictionary, say output, whose keys 
        are integers in [0, len(self.__waveforms) - 1]. 
        ouptut[i] matches the output of 
        self.__waveforms[i].analyse(...), which is a dictionary. 
        I.e. the output of this method is a dictionary of 
        dictionaries.

        Parameters
        ----------
        label : str
            For every analysed waveform, this is the key
            for the new WfAna object within its Analyses
            attribute.
        analyser_name : str
            It must match the name of a WfAna method whose first            
            argument must be called 'waveform' and whose type       # The only way to import the WaveformAdcs class in WfAna without having     # This would not be a problem (and we would not    
            annotation must match the WaveformAdcs class or the     # a circular import is to use the typing.TYPE_CHECKING variable, which      # need to grab the analyser method using an 
            'WaveformAdcs' string literal. Such method should       # is only defined for type-checking runs. As a consequence, the type        # string and getattr) if the analyser methods were
            also have a defined return-annotation which must        # annotation should be an string, which the type-checking software          # defined as WaveformAdcs methods or in a separate
            match Tuple[WfAnaResult, bool, dict].                   # successfully associates to the class itself, but which is detected        # module. There might be other downsizes to it such
                                                                    # as so (a string) by inspect.signature().                                  #  as the accesibility to WfAna attributes.
        baseline_limits : list of int
            For every analysed waveform, say wf, it 
            defines the Adcs points which will be used 
            for baseline calculation (it is given to
            the 'baseline_limits' parameter of
            Waveform.analyse() - actually 
            WaveformAdcs.analyse()). It must have an 
            even number of integers which must meet 
            baseline_limits[i] < baseline_limits[i + 1] 
            for all i. The points which are used for 
            baseline calculation are 
            wf.Adcs[baseline_limits[2*i]:baseline_limits[(2*i) + 1]],
            with i = 0,1,...,(len(baseline_limits)/2) - 1. 
            The upper limits are exclusive. For more 
            information check the 'baseline_limits' 
            parameter documentation in the 
            Waveform.analyse() docstring.
        *args
            For each analysed waveform, these are the 
            positional arguments which are given to the
            analyser method by WaveformAdcs.analyse().
        int_ll (resp. int_ul): int
            For every analysed waveform, it defines the
            integration window (it is given to the 'int_ll'
            (resp. 'int_ul') parameter of Waveform.analyse()
            - actually WaveformAdcs.analyse()). int_ll must 
            be smaller than int_ul. These limits are 
            inclusive. If they are not defined, then the
            whole Adcs are considered for each waveform. 
            For more information check the 'int_ll' and 
            'int_ul' parameters documentation in the 
            Waveform.analyse() docstring.
        overwrite : bool
            If True, for every analysed Waveform wf, its
            'analyse' method will overwrite any existing
            WfAna object with the same label (key) within
            its Analyses attribute.
        **kwargs
            For each analysed waveform, these are the
            keyword arguments which are given to the
            analyser method by WaveformAdcs.analyse().

        Returns
        ----------
        output : dict
            output[i] gives the output of 
            self.__waveforms[i].analyse(...), which is a
            dictionary containing any additional information
            of the analysis which was performed over the
            i-th waveform of this WaveformSet. Such 
            dictionary is empty if the analyser method gives 
            no additional information.
        """

        if not self.baseline_limits_are_well_formed(baseline_limits):
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.analyse()',
                                                        f"The baseline limits ({baseline_limits}) are not well formed."))
        int_ul_ = int_ul
        if int_ul_ is None:
            int_ul_ = self.PointsPerWf - 1

        if not self.subinterval_is_well_formed(int_ll, int_ul_):
            raise Exception(generate_exception_message( 2,
                                                        'WaveformSet.analyse()',
                                                        f"The integration window ({int_ll}, {int_ul_}) is not well formed."))
        aux = WfAna([0,1],  # Dummy object to access
                    0,      # the analyser instance method
                    1,)
        try:
            analyser = getattr(aux, analyser_name)
        except AttributeError:
            raise Exception(generate_exception_message( 3,
                                                        'WaveformSet.analyse()',
                                                        f"The analyser method '{analyser_name}' does not exist in the WfAna class."))
        try:
            signature = inspect.signature(analyser)
        except TypeError:
            raise Exception(generate_exception_message( 4,
                                                        'WaveformSet.analyse()',
                                                        f"'{analyser_name}' does not match a callable attribute of WfAna."))
        try:
            if list(signature.parameters.keys())[0] != 'waveform':
                raise Exception(generate_exception_message( 5,
                                                            "WaveformSet.analyse()",
                                                            "The name of the first parameter of the given analyser method must be 'waveform'."))
            
            if signature.parameters['waveform'].annotation not in ['WaveformAdcs', WaveformAdcs]:
                raise Exception(generate_exception_message( 6,
                                                            "WaveformSet.analyse()",
                                                            "The 'waveform' parameter of the analyser method must be hinted as a WaveformAdcs object."))
            
            if signature.return_annotation != Tuple[WfAnaResult, bool, dict]:
                raise Exception(generate_exception_message( 7,
                                                            "WaveformSet.analyse()",
                                                            "The return type of the analyser method must be hinted as Tuple[WfAnaResult, bool, dict]."))
        except IndexError:
            raise Exception(generate_exception_message( 8,
                                                        "WaveformSet.analyse()",
                                                        'The given analyser method must take at least one parameter.'))
        output = {}

        for i in range(len(self.__waveforms)):
            output[i] = self.__waveforms[i].analyse(    label,
                                                        analyser_name,
                                                        baseline_limits,
                                                        *args,
                                                        int_ll = int_ll,
                                                        int_ul = int_ul_,
                                                        overwrite = overwrite,
                                                        **kwargs)
        return output
    
    def baseline_limits_are_well_formed(self, baseline_limits : List[int]) -> bool:

        """
        This method returns True if len(baseline_limits) is even and 
        0 <= baseline_limits[0] < baseline_limits[1] < ... < baseline_limits[-1] <= self.PointsPerWf - 1.
        It returns False if else.

        Parameters
        ----------
        baseline_limits : list of int

        Returns
        ----------
        bool
        """

        if len(baseline_limits)%2 != 0:
            return False

        if baseline_limits[0] < 0:
            return False
            
        for i in range(0, len(baseline_limits) - 1):
            if baseline_limits[i] >= baseline_limits[i + 1]:
                return False
                
        if baseline_limits[-1] > self.PointsPerWf - 1:
            return False
        
        return True
    
    def subinterval_is_well_formed(self,    i_low : int, 
                                            i_up : int) -> bool:
        
        """
        This method returns True if 0 <= i_low < i_up <= self.PointsPerWf - 1,
        and False if else.

        Parameters
        ----------
        i_low : int
        i_up : int

        Returns
        ----------
        bool
        """

        if i_low < 0:
            return False
        elif i_up <= i_low:
            return False
        elif i_up > self.PointsPerWf - 1:
            return False
        
        return True
    
    def plot(self,  nrows : int = 1,
                    ncols : int = 1,
                    figure : Optional[pgo.Figure] = None,
                    wfs_per_axes : Optional[int] = 1,
                    grid_of_wf_idcs : Optional[List[List[List[int]]]] = None,
                    average : bool = False,
                    share_x_scale : bool = False,
                    share_y_scale : bool = False,
                    plot_analysis_markers : bool = False,
                    show_baseline_limits : bool = False, 
                    show_baseline : bool = True,
                    show_general_integration_limits : bool = False,
                    show_spotted_peaks : bool = True,
                    show_peaks_integration_limits : bool = False,
                    analysis_label : Optional[str] = None) -> pgo.Figure: 


        """ 
        This method returns a plotly.graph_objects.Figure 
        with a nrows x ncols grid of axes, with plots of
        some of the waveforms in this WaveformSet object.

        Parameters
        ----------
        nrows (resp. ncols) : int
            Number of rows (resp. columns) of the returned 
            grid of axes.
        figure : plotly.graph_objects.Figure
            If it is not None, then it must be have been
            generated using plotly.subplots.make_subplots()
            (even if nrows and ncols equal 1). It is the
            caller's responsibility to ensure this.
            If that's the case, then this method adds the
            plots to this figure and eventually returns 
            it. In such case, the number of rows (resp. 
            columns) in such figure must match the 'nrows' 
            (resp. 'ncols') parameter.
        wfs_per_axes : int
            If it is not None, then the argument given to 
            'grid_of_wf_idcs' will be ignored. In this case,
            the number of waveforms considered for each
            axes is wfs_per_axes. P.e. for wfs_per_axes 
            equal to 2, the axes at the first row and first
            column contains information about the first
            two waveforms in the set. The axes in the first 
            row and second column will consider the 
            following two, and so on.
        grid_of_wf_idcs : list of list of list of int
            This list must contain nrows lists, each of which
            must contain ncols lists of integers. 
            grid_of_wf_idcs[i][j] gives the indices of the 
            waveforms, with respect to this WaveformSet, which
            should be considered for plotting in the axes
            which are located at the i-th row and j-th column.
        average : bool
            If True, instead of plotting all of the specified
            waveforms, up to the 'wvfs_per_axes' and the
            'grid_of_wf_idcs' parameters, the average waveform
            of the considered waveforms will be plotted.
            If False, all of the considered waveforms will be
            plotted.
        share_x_scale (resp. share_y_scale) : bool
            If True, the x-axis (resp. y-axis) scale will be 
            shared among all the subplots.
        plot_analysis_markers : bool
            This parameter is given to the 'plot_analysis_markers' 
            argument of the Waveform.plot() method for each 
            waveform in this WaveformSet. If True, analysis 
            markers for the plotted WaveformAdcs objects 
            will potentially be plotted together with each 
            waveform. For more information, check the 
            'plot_analysis_markers' parameter documentation 
            in the Waveform.plot() method. If False, no analysis 
            markers will be plot.
        show_baseline_limits : bool
            This parameter only makes a difference if
            'plot_analysis_markers' is set to True. In that 
            case, this parameter means whether to plot 
            vertical lines framing the intervals which 
            were used to compute the baseline.
        show_baseline : bool
            This parameter only makes a difference if
            'plot_analysis_markers' is set to True. In that 
            case, this parameter means whether to plot an 
            horizontal line matching the computed baseline
        show_general_integration_limits : bool
            This parameter only makes a difference if
            'plot_analysis_markers' is set to True. In that 
            case, this parameter means whether to plot vertical 
            lines framing the general integration interval.
        show_spotted_peaks : bool
            This parameter only makes a difference if
            'plot_analysis_markers' is set to True. In that 
            case, this parameter means whether to plot a 
            triangle marker over each spotted peak.
        show_peaks_integration_limits : bool
            This parameter only makes a difference if
            'plot_analysis_markers' is set to True. In that 
            case, this parameter means whether to plot two 
            vertical lines framing the integration interval 
            for each spotted peak.
        analysis_label : str
            This parameter is given to the 'analysis_label' 
            parameter of the Waveform.plot() (actually 
            WaveformAdcs.plot()) method for each WaveformAdcs
            object which will be plotted. It only makes a 
            difference if 'plot_analysis_markers' is set to 
            True. In that case, 'analysis_label' is the key 
            for the WfAna object within the Analysis attribute 
            of each plotted waveform from where to take the 
            information for the analysis markers plot. If 
            'analysis_label' is None, then the last analysis 
            added to self.__analyses will be the used one.            

        Returns
        ----------
        figure : plotly.graph_objects.Figure
            The figure with the grid plot of the waveforms
        """

        if nrows < 1 or ncols < 1:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.plot()',
                                                        'The number of rows and columns must be positive.'))
        fFigureIsGiven = False
        if figure is not None:

            try:
                fig_rows, fig_cols = figure._get_subplot_rows_columns() # Returns two range objects
                fig_rows, fig_cols = list(fig_rows)[-1], list(fig_cols)[-1]

            except Exception:   # Happens if figure was not created using plotly.subplots.make_subplots

                raise Exception(generate_exception_message( 2,
                                                            'WaveformSet.plot()',
                                                            'The given figure is not a subplot grid.'))
            if fig_rows != nrows or fig_cols != ncols:
                
                raise Exception(generate_exception_message( 3,
                                                            'WaveformSet.plot()',
                                                            f"The number of rows and columns in the given figure ({fig_rows}, {fig_cols}) must match the nrows ({nrows}) and ncols ({ncols}) parameters."))
            fFigureIsGiven = True

        grid_of_wf_idcs_ = None         # Logically useless

        if wfs_per_axes is not None:    # wfs_per_axes is defined

            if wfs_per_axes < 1:
                raise Exception(generate_exception_message( 4,
                                                            'WaveformSet.plot()',
                                                            'The number of waveforms per axes must be positive.'))

            grid_of_wf_idcs_ = self.get_grid_of_wf_idcs(nrows,
                                                        ncols,
                                                        wfs_per_axes = wfs_per_axes)

        elif grid_of_wf_idcs is None:   # Nor wf_per_axes, nor 
                                        # grid_of_wf_idcs are defined

            raise Exception(generate_exception_message( 5,
                                                        'WaveformSet.plot()',
                                                        "The 'grid_of_wf_idcs' parameter must be defined if wfs_per_axes is not."))
        
        elif not WaveformSet.grid_of_lists_is_well_formed(  grid_of_wf_idcs,    # wf_per_axes is not defined, 
                                                            nrows,              # but grid_of_wf_idcs is, but 
                                                            ncols):             # it is not well-formed
            raise Exception(generate_exception_message( 6,
                                                        'WaveformSet.plot()',
                                                        f"The given grid_of_wf_idcs is not well-formed according to nrows ({nrows}) and ncols ({ncols})."))
        else:   # wf_per_axes is not defined,
                # but grid_of_wf_idcs is,
                # and it is well-formed

            grid_of_wf_idcs_ = grid_of_wf_idcs

        if not fFigureIsGiven:
            
            figure_ = psu.make_subplots(    rows = nrows, 
                                            cols = ncols)
        else:
            figure_ = figure

        WaveformSet.update_shared_axes_status(  figure_,                    # An alternative way is to specify 
                                                share_x = share_x_scale,    # shared_xaxes=True (or share_yaxes=True)
                                                share_y = share_y_scale)    # in psu.make_subplots(), but, for us, 
                                                                            # that alternative is only doable for 
                                                                            # the case where the given 'figure'
                                                                            # parameter is None.
        if not average:                                                                            
            for i in range(nrows):
                for j in range(ncols):
                    for k in grid_of_wf_idcs_[i][j]:

                        self.__waveforms[k].plot(   figure = figure_,
                                                    name = f"Wf {k}, Ch {self.__waveforms[k].Channel}, Ep {self.__waveforms[k].Endpoint}",
                                                    row = i + 1,  # Plotly uses 1-based indexing
                                                    col = j + 1,
                                                    plot_analysis_markers = plot_analysis_markers,
                                                    show_baseline_limits = show_baseline_limits,
                                                    show_baseline = show_baseline,
                                                    show_general_integration_limits = show_general_integration_limits,
                                                    show_spotted_peaks = show_spotted_peaks,
                                                    show_peaks_integration_limits = show_peaks_integration_limits,
                                                    analysis_label = analysis_label)
        else:
            for i in range(nrows):
                for j in range(ncols):

                    aux = self.compute_mean_waveform(wf_idcs = grid_of_wf_idcs_[i][j])  # WaveformSet.compute_mean_waveform() will
                                                                                        # raise an exception if grid_of_wf_idcs_[i][j]
                                                                                        # happens to be empty

                    aux_name = 'Mean Wf ['+ WaveformSet.get_string_of_first_n_integers_if_available(grid_of_wf_idcs_[i][j],
                                                                                                    queried_no = 3) + ']'
                    aux.plot(   figure = figure_,
                                name = aux_name,
                                row = i + 1,
                                col = j + 1,
                                plot_analysis_markers = plot_analysis_markers,
                                show_baseline_limits = show_baseline_limits,
                                show_baseline = show_baseline,
                                show_general_integration_limits = show_general_integration_limits,
                                show_spotted_peaks = show_spotted_peaks,
                                show_peaks_integration_limits = show_peaks_integration_limits,
                                analysis_label = analysis_label)
        return figure_

    @staticmethod
    def get_string_of_first_n_integers_if_available(input_list : List[int],
                                                    queried_no : int = 3) -> str:

        """
        This method returns an string with the first
        comma-separated n integers of the given list
        where n is the minimum between queried_no and 
        the length of the given list, input_list. If 
        n is 0, then the output is an empty string. 
        If n equals queried_no, (i.e. if queried_no
        is smaller than the length of the input list) 
        then the ',...' string is appended to the 
        output.

        Parameters
        ----------
        input_list : list of int
        queried_no : int
            It must be a positive integer

        Returns
        ----------
        output : str
        """

        if queried_no < 1:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.get_string_of_first_n_integers_if_available()',
                                                        f"The given queried_no ({queried_no}) must be positive."))
        actual_no = queried_no
        fAppend = True

        if queried_no > len(input_list):
            actual_no = len(input_list)
            fAppend = False

        output = ''

        for i in range(actual_no):
            output += (str(input_list[i])+',')

        output = output[:-1] if not fAppend else (output[:-1] + ',...')

        return output
    
    @staticmethod
    def update_shared_axes_status(  figure : pgo.Figure,
                                    share_x : bool = False,
                                    share_y : bool = True) -> pgo.Figure:
        
        """
        If share_x (resp. share_y) is True, then this
        method makes the x-axis (resp. y-axis) scale 
        of every subplot in the given figure shared.
        If share_x (resp. share_y) is False, then this
        method will reset the shared-status of the 
        x-axis (resp. y-axis) so that they are not 
        shared anymore. Finally, it returns the figure 
        with the shared y-axes.

        Parameters
        ----------
        figure : plotly.graph_objects.Figure
            The figure whose subplots will share the
            selected axes scale.
        share_x (resp. share_y): bool
            If True, the x-axis (resp. y-axis) scale will be
            shared among all the subplots. If False, the
            x-axis (resp. y-axis) scale will not be shared
            anymore.
        
        Returns
        ----------
        figure : plotly.graph_objects.Figure
        """
        
        try:
            fig_rows, fig_cols = figure._get_subplot_rows_columns() # Returns two range objects
        except Exception:   # Happens if figure was not created using plotly.subplots.make_subplots
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.update_shared_axes_status()',
                                                        'The given figure is not a subplot grid.'))
        
        fig_rows, fig_cols = list(fig_rows)[-1], list(fig_cols)[-1]

        aux_x = None if not share_x else 'x'
        aux_y = None if not share_y else 'y'
        
        for i in range(fig_rows):
            for j in range(fig_cols):
                figure.update_xaxes(matches=aux_x, row=i+1, col=j+1)
                figure.update_yaxes(matches=aux_y, row=i+1, col=j+1)

        return figure

    @staticmethod
    def grid_of_lists_is_well_formed(   grid : List[List[List]],
                                        nrows : int,
                                        ncols : int) -> bool:
        
        """
        This method returns True if the given grid contains
        nrows lists, each of which contains ncols lists. It 
        returns False if else.

        Parameters
        ----------
        grid : list of lists of lists
        nrows : int
        ncols : int

        Returns
        ----------
        bool
        """

        if nrows < 1 or ncols < 1:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.grid_of_lists_is_well_formed()',
                                                        'The number of rows and columns must be positive.'))
        if len(grid) != nrows:
            return False
        else:
            for row in grid:
                if len(row) != ncols:
                    return False
        return True

    def get_grid_of_wf_idcs(self,   nrows : int,
                                    ncols : int,
                                    wfs_per_axes : Optional[int] = None,
                                    wf_filter : Optional[Callable[..., bool]] = None,
                                    filter_args : Optional[List[List[List]]] = None,
                                    max_wfs_per_axes : Optional[int] = 5) -> List[List[List[int]]]:
        
        """
        This method returns a list of lists of lists of integers,
        which should be interpreted as iterator values for
        waveforms in this WaveformSet object.

        Parameters
        ----------
        nrows : int
            The length of the returned list.
        ncols : 
            The length of every list within the returned 
            list.
        wfs_per_axes : int
            If it is not None, then it must be a positive
            integer, so that the iterator values contained 
            in the output grid are contiguous in
            [0, nrows*ncols*wfs_per_axes - 1]. I.e.
            output[0][0] contains 0, 1, ... , wfs_per_axes - 1,
            output[0][1] contains wfs_per_axes, wfs_per_axes + 1,
            ... , 2*wfs_per_axes - 1, and so on. 
        wf_filter : callable
            This parameter only makes a difference if
            the 'wfs_per_axes' parameter is None. In such
            case, this one must be a callable object whose 
            first parameter must be called 'waveform' and 
            must be hinted as a Waveform object. Also, the
            return type of such callable must be annotated
            as a boolean. If wf_filter is 
                - WaveformSet.match_run or
                - WaveformSet.match_endpoint_and_channel,
            this method can benefit from the information in
            self.Runs and self.AvailableChannels and its
            execution time may be reduced with respect to
            the case where an arbitrary (but compliant) 
            callable is passed to wf_filter.
        filter_args : list of list of list
            This parameter only makes a difference if 
            the 'wfs_per_axes' parameter is None. In such
            case, this parameter must be defined and
            it must contain nrows lists, each of which
            must contain ncols lists. filter_args[i][j],
            for all i and j, is interpreted as a list of
            arguments which will be given to wf_filter
            at some point. The user is responsible for
            giving a set of arguments which comply with
            the signature of the specified wf_filter.
            For more information check the return value 
            documentation.
        max_wfs_per_axes : int
            This parameter only makes a difference if           ## If max_wfs_per_axes applies and 
            the 'wfs_per_axes' parameter is None. In such       ## is a positive integer, it is never
            case, and if 'max_wfs_per_axes' is not None,        ## checked that there are enough waveforms
            then output[i][j] will contain the indices for      ## in the WaveformSet to fill the grid.
            the first max_wfs_per_axes waveforms in this        ## This is an open issue.
            WaveformSet which passed the filter. If it is 
            None, then this function iterates through the 
            whole WaveformSet for every i,j pair. Note that 
            setting this parameter to None may result in a 
            long execution time.

        Returns
        ----------
        output : list of list of list of int
            If the 'wfs_per_axes' parameter is defined, then
            the iterator values contained in the output grid 
            are contiguous in [0, nrows*ncols*wfs_per_axes - 1].
            For more information, check the 'wfs_per_axes'
            parameter documentation. If the 'wfs_per_axes'
            is not defined, then the 'wf_filter' and 'filter_args'
            parameters must be defined and output[i][j] gives 
            the indices of the waveforms in this WaveformSet 
            object, say wf, for which 
            wf_filter(wf, *filter_args[i][j]) returns True.
            In this last case, the number of indices in each
            grid slot may be limited, up to the value given
            to the 'max_wfs_per_axes' parameter.
        """

        if nrows < 1 or ncols < 1:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.get_grid_of_wf_idcs()',
                                                        'The number of rows and columns must be positive.'))
        fFilteringMode = True
        if wfs_per_axes is not None:
            if wfs_per_axes < 1:
                raise Exception(generate_exception_message( 2,
                                                            'WaveformSet.get_grid_of_wf_idcs()',
                                                            f"The given wfs_per_axes ({wfs_per_axes}) must be positive."))
            fFilteringMode = False

        fMaxIsSet = None    # This one should only be defined as
                            # a boolean if fFilteringMode is True
        if fFilteringMode:

            try:
                signature = inspect.signature(wf_filter)
            except TypeError:
                raise Exception(generate_exception_message( 3,
                                                            'WaveformSet.get_grid_of_wf_idcs()',
                                                            "The given wf_filter is not defined or is not callable. It must be suitably defined because the 'wfs_per_axes' parameter is not. At least one of them must be suitably defined."))

            if list(signature.parameters.keys())[0] != 'waveform':
                raise Exception(generate_exception_message( 4,
                                                            'WaveformSet.get_grid_of_wf_idcs()',
                                                            "The name of the first parameter of the given filter must be 'waveform'."))
            
            if signature.parameters['waveform'].annotation != Waveform:
                raise Exception(generate_exception_message( 5,
                                                            'WaveformSet.get_grid_of_wf_idcs()',
                                                            "The 'waveform' parameter of the filter must be hinted as a Waveform object."))
            if filter_args is None:
                raise Exception(generate_exception_message( 6,
                                                            'WaveformSet.get_grid_of_wf_idcs()',
                                                            "The 'filter_args' parameter must be defined if the 'wfs_per_axes' parameter is not."))
            
            elif not WaveformSet.grid_of_lists_is_well_formed(  filter_args,
                                                                nrows,
                                                                ncols):
                    
                    raise Exception(generate_exception_message( 7,
                                                                'WaveformSet.get_grid_of_wf_idcs()',
                                                                f"The shape of the given filter_args list is not nrows ({nrows}) x ncols ({ncols})."))
            fMaxIsSet = False
            if max_wfs_per_axes is not None:
                if max_wfs_per_axes < 1:
                    raise Exception(generate_exception_message( 8,
                                                                'WaveformSet.get_grid_of_wf_idcs()',
                                                                f"The given max_wfs_per_axes ({max_wfs_per_axes}) must be positive."))
                fMaxIsSet = True

        if not fFilteringMode:

            return WaveformSet.get_2D_indices_nested_list(  wfs_per_axes,
                                                            nrows = nrows,
                                                            ncols = ncols)
            
        else:   # fFilteringMode is True and so, wf_filter, 
                # filter_args and fMaxIsSet are defined

            mode_map = {WaveformSet.match_run : 0,
                        WaveformSet.match_endpoint_and_channel : 1}
            try:
                fMode = mode_map[wf_filter]
            except KeyError:
                fMode = 2

            output = WaveformSet.get_2D_empty_nested_list(nrows, ncols)

            if fMode == 0:
                return self.__get_grid_of_wf_idcs_by_run(   output,
                                                            filter_args,
                                                            fMaxIsSet,
                                                            max_wfs_per_axes)
            elif fMode == 1:
                return self.__get_grid_of_wf_idcs_by_endpoint_and_channel(  output,
                                                                            filter_args,
                                                                            fMaxIsSet,
                                                                            max_wfs_per_axes)
            else:
                return self.__get_grid_of_wf_idcs_general(  output,
                                                            wf_filter,
                                                            filter_args,
                                                            fMaxIsSet,
                                                            max_wfs_per_axes)

    @staticmethod
    def match_run(  waveform : Waveform,
                    run : int) -> bool:
        
        """
        This method returns True if the RunNumber attribute
        of the given Waveform object matches run. It returns 
        False if else.

        Parameters
        ----------
        waveform : Waveform
        run : int

        Returns
        ----------
        bool
        """

        return waveform.RunNumber == run
    
    @staticmethod
    def match_channel(  waveform : Waveform,
                        channel : int) -> bool:
        
        """
        This method returns True if the Channel attribute
        of the given Waveform object matches channel, and 
        False if else.

        Parameters
        ----------
        waveform : Waveform
        channel : int

        Returns
        ----------
        bool
        """

        return waveform.Channel == channel
    
    @staticmethod
    def match_endpoint_and_channel( waveform : Waveform,
                                    endpoint : int,
                                    channel : int) -> bool:
        
        """
        This method returns True if the Endpoint and Channel
        attributes of the given Waveform object match endpoint 
        and channel, respectively.

        Parameters
        ----------
        waveform : Waveform
        endpoint : int
        channel : int

        Returns
        ----------
        bool
        """

        return waveform.Endpoint == endpoint and waveform.Channel == channel
    
    def __get_grid_of_wf_idcs_by_run(self,  blank_grid : List[List[List]],
                                            filter_args : List[List[List]],
                                            fMaxIsSet : bool,
                                            max_wfs_per_axes : Optional[int] = 5) -> List[List[List[int]]]:
        
        """
        This method should only be called by the
        WaveformSet.get_grid_of_wf_idcs() method, where
        the well-formedness checks of the input have
        already been performed. This method generates an
        output as described in such method docstring,
        for the case when wf_filter is WaveformSet.match_run.
        Refer to the WaveformSet.get_grid_of_wf_idcs()
        method documentation for more information.

        Parameters
        ----------
        blank_grid : list of list of list
        filter_args : list of list of list
        fMaxIsSet : bool
        max_wfs_per_axes : int

        Returns
        ----------
        list of list of list of int
        """

        for i in range(len(blank_grid)):
            for j in range(len(blank_grid[i])):

                if filter_args[i][j][0] not in self.__runs:
                    continue

                if fMaxIsSet:   # blank_grid should not be very big (visualization purposes)
                                # so we can afford evaluating the fMaxIsSet conditional here
                                # instead of at the beginning of the method (which would
                                # be more efficient but would entail a more extensive code)

                    counter = 0
                    for k in range(len(self.__waveforms)):
                        if WaveformSet.match_run(   self.__waveforms[k],
                                                    *filter_args[i][j]):
                            blank_grid[i][j].append(k)
                            counter += 1
                            if counter == max_wfs_per_axes:
                                break
                else:
                    for k in range(len(self.__waveforms)):
                        if WaveformSet.match_run(   self.__waveforms[k],
                                                    *filter_args[i][j]):
                            blank_grid[i][j].append(k)        
        return blank_grid
    
    def __get_grid_of_wf_idcs_by_endpoint_and_channel(self, blank_grid : List[List[List]],
                                                            filter_args : List[List[List]],
                                                            fMaxIsSet : bool,
                                                            max_wfs_per_axes : Optional[int] = 5) -> List[List[List[int]]]:
        
        """
        This method should only be called by the 
        WaveformSet.get_grid_of_wf_idcs() method, where 
        the well-formedness checks of the input have 
        already been performed. This method generates an 
        output as described in such method docstring,
        for the case when wf_filter is 
        WaveformSet.match_endpoint_and_channel. Refer to
        the WaveformSet.get_grid_of_wf_idcs() method
        documentation for more information.

        Parameters
        ----------
        blank_grid : list of list of list
        filter_args : list of list of list
        fMaxIsSet : bool
        max_wfs_per_axes : int

        Returns
        ----------
        list of list of list of int
        """

        for i in range(len(blank_grid)):
            for j in range(len(blank_grid[i])):

                if filter_args[i][j][0] not in self.__available_channels.keys():    # filter_args[i][j][0] is the
                    continue                                                        # endpoint we are looking for

                elif filter_args[i][j][1] not in self.__available_channels[filter_args[i][j][0]]:   # filter_args[i][j][1] is
                    continue                                                                        # the channel of endpoint 
                                                                                                    # filter_args[i][j][0]
                                                                                                    # which we are looking for
                if fMaxIsSet:   # blank_grid should not be very big (visualization purposes)
                                # so we can afford evaluating the fMaxIsSet conditional here
                                # instead of at the beginning of the method (which would
                                # be more efficient but would entail a more extensive code)

                    counter = 0
                    for k in range(len(self.__waveforms)):
                        if WaveformSet.match_endpoint_and_channel(  self.__waveforms[k],
                                                                    *filter_args[i][j]):
                            blank_grid[i][j].append(k)
                            counter += 1
                            if counter == max_wfs_per_axes:
                                break
                else:
                    for k in range(len(self.__waveforms)):
                        if WaveformSet.match_endpoint_and_channel(  self.__waveforms[k],
                                                                    *filter_args[i][j]):
                            blank_grid[i][j].append(k)
        return blank_grid
    
    def __get_grid_of_wf_idcs_general(self, blank_grid : List[List[List]],
                                            wf_filter : Callable[..., bool],
                                            filter_args : List[List[List]],
                                            fMaxIsSet : bool,
                                            max_wfs_per_axes : Optional[int] = 5) -> List[List[List[int]]]:
        
        """
        This method should only be called by the 
        WaveformSet.get_grid_of_wf_idcs() method, where 
        the well-formedness checks of the input have 
        already been performed. This method generates an 
        output as described in such method docstring,
        for the case when wf_filter is neither
        WaveformSet.match_run nor
        WaveformSet.match_endpoint_and_channel. Refer 
        to the WaveformSet.get_grid_of_wf_idcs() method
        documentation for more information.

        Parameters
        ----------
        blank_grid : list of list of list
        wf_filter : callable
        filter_args : list of list of list
        fMaxIsSet : bool
        max_wfs_per_axes : int

        Returns
        ----------
        list of list of list of int
        """

        for i in range(len(blank_grid)):
            for j in range(len(blank_grid[i])):

                if fMaxIsSet:
                    counter = 0
                    for k in range(len(self.__waveforms)):
                        if wf_filter(   self.__waveforms[k],
                                        *filter_args[i][j]):
                            
                            blank_grid[i][j].append(k)
                            counter += 1
                            if counter == max_wfs_per_axes:
                                break
                else:
                    for k in range(len(self.__waveforms)):
                        if wf_filter(   self.__waveforms[k],
                                        *filter_args[i][j]):
                            blank_grid[i][j].append(k)
        return blank_grid
                            
    @staticmethod
    def get_2D_empty_nested_list(   nrows : int = 1,
                                    ncols : int = 1) -> List[List[List]]:
        
        """
        This method returns a 2D nested list of empty lists
        with nrows rows and ncols columns.
        
        Parameters
        ----------
        nrows (resp. ncols) : int
            Number of rows (resp. columns) of the returned 
            nested list.

        Returns
        ----------
        list of list of list
            A list containing nrows lists, each of them
            containing ncols empty lists.
        """

        if nrows < 1 or ncols < 1:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.get_2D_empty_nested_list()',
                                                        'The number of rows and columns must be positive.'))

        return [[[] for _ in range(ncols)] for _ in range(nrows)]
    
    @staticmethod
    def get_2D_indices_nested_list( indices_per_slot : int,
                                    nrows : int = 1,
                                    ncols : int = 1) -> List[List[List]]:
        
        """
        This method returns a 2D nested list with nrows
        rows and ncols columns. Such nested list, say
        output, contains contiguous positive integers in
        [0, nrows*ncols*indices_per_slot - 1]. I.e.
        output[0][0] contains 0, 1, ... , indices_per_slot - 1,
        output[0][1] contains indices_per_slot, 
        indices_per_slot + 1, ...  , 2*indices_per_slot - 1, 
        and so on. 
        
        Parameters
        ----------
        indices_per_slot : int
            The number of indices contained within each 
            slot in the returned output grid
        nrows (resp. ncols) : int
            Number of rows (resp. columns) of the returned 
            nested list

        Returns
        ----------
        list of list of list
            A list containing nrows lists, each of them
            containing ncols lists, each of them containing
            indices_per_slot integers.
        """

        if nrows < 1 or ncols < 1:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.get_2D_indices_nested_list()',
                                                        f"The given number of rows ({nrows}) and columns ({ncols}) must be positive."))
        if indices_per_slot < 1:
            raise Exception(generate_exception_message( 2,
                                                        'WaveformSet.get_2D_indices_nested_list()',
                                                        f"The given number of indices per slot ({indices_per_slot}) must be positive."))
        
        return [[[k + indices_per_slot*(j + (ncols*i)) for k in range(indices_per_slot)] for j in range(ncols)] for i in range(nrows)]

    @classmethod
    def from_ROOT_file(cls, filepath : str,
                            tree_to_look_for : str ='raw_waveforms',
                            start_fraction : float = 0.0,
                            stop_fraction : float = 1.0) -> 'WaveformSet':

        """
        Alternative initializer for a WaveformSet object out of the
        waveforms stored in a ROOT file

        Parameters
        ----------
        filepath : str
            Path to the ROOT file to be read. Such ROOT file should 
            have a defined TTree object whose name matches tree_to_look_for.
            Such TTree should have at least three branches, with names
            'channel', 'timestamp', 'adcs', from which the values for           ## For the moment, the timestamp branch may
            the Waveform objects attributes Channel, Timestamp and Adcs         ## be called 'timestamps'
            will be taken respectively.
        tree_to_look_for : str
            Name of the tree which will be extracted from the given
            ROOT file
        start_fraction (resp. stop_fraction) : float
            Gives the iterator value for the first (resp. last) waveform
            which will be loaded into this WaveformSet object. P.e. 
            setting start_fraction to 0.5 and stop_fraction to 0.75 
            will result in loading the waveforms that belong to the 
            third quarter of the input file.
        """

        if not WaveformSet.fraction_is_well_formed(start_fraction, stop_fraction):
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.from_ROOT_file()',
                                                        f"Fraction limits are not well-formed"))
        input_file = uproot.open(filepath)

        try:
            aux = input_file[tree_to_look_for+';1']     # Assuming that ROOT appends
        except KeyError:                                # ';1' to its trees names
            raise Exception(generate_exception_message( 2,
                                                        'WaveformSet.from_ROOT_file()',
                                                        f"TTree {tree_to_look_for} not found in {filepath}"))
        if 'channel' not in aux.keys():
            raise Exception(generate_exception_message( 3,
                                                        'WaveformSet.from_ROOT_file()',
                                                        f"Branch 'channel' not found in the given TTree"))
        if 'timestamp' not in aux.keys() and 'timestamps' not in aux.keys():    ## Temporal
            raise Exception(generate_exception_message( 4,
                                                        'WaveformSet.from_ROOT_file()',
                                                        f"Branch 'timestamp' not found in the given TTree"))
        if 'adcs' not in aux.keys():
            raise Exception(generate_exception_message( 5,
                                                        'WaveformSet.from_ROOT_file()',
                                                        f"Branch 'adcs' not found in the given TTree"))
        
        adcs = aux['adcs']  # adcs is an uproot.TBranch object

        wf_start = math.floor(start_fraction*adcs.num_entries)
        wf_stop = math.ceil(stop_fraction*adcs.num_entries)

        channels = aux['channel'].array(entry_start = wf_start, 
                                        entry_stop = wf_stop)         # It is slightly faster (~106s vs. 114s, for a
                                                                    # 809 MB input file running on lxplus9) to read
        adcs = aux['adcs'].array(   entry_start = wf_start,           # branch by branch rather than going for aux.arrays()
                                    entry_stop = wf_stop)          
        try:
            timestamps = aux['timestamp'].array(entry_start = wf_start,
                                                entry_stop = wf_stop)   
        except uproot.exceptions.KeyInFileError:    
            timestamps = aux['timestamps'].array(   entry_start = wf_start,
                                                    entry_stop = wf_stop) ## Temporal

        waveforms = []                  # Using a list comprehension here is slightly slower than a for loop
        for i in range(len(adcs)):      # (97s vs 102s for 5% of wvfs of a 809 MB file running on lxplus9)

            endpoint, channel = WaveformSet.get_endpoint_and_channel(channels[i])

            waveforms.append(Waveform(  timestamps[i],
                                        0,      # TimeStep_ns   ## To be implemented from the new
                                                                ## 'metadata' TTree in the ROOT file
                                        np.array(adcs[i]),
                                        0,      #RunNumber      ## To be implemented from the new
                                                                ## 'metadata' TTree in the ROOT file
                                        endpoint,
                                        channel))      
        return cls(*waveforms)

    @staticmethod
    def get_endpoint_and_channel(input : int) -> Tuple[int, int]:
    
        """
        Parameters
        ----------
        input : str
            len(input) must be 5. Such input is interpreted as the
            concatenation of the endpoint int(input[0:3]) and the 
            channel int(input[3:5]).

        Returns
        ----------
        int
            The endpoint value
        int
            The channel value
        """

        return int(str(input)[0:3]), int(str(input)[3:5])
    
    @staticmethod
    def fraction_is_well_formed(lower_limit : float = 0.0,
                                upper_limit : float = 1.0) -> bool:
        
        """
        This method returns True if 0.0 <= lower_limit < upper_limit <= 1.0,
        and False if else.

        Parameters
        ----------
        lower_limit : float
        upper_limit : float

        Returns
        ----------
        bool
        """

        if lower_limit < 0.0:
            return False
        elif upper_limit <= lower_limit:
            return False
        elif upper_limit > 1.0:
            return False
        
        return True
    
    def compute_mean_waveform(self, *args,
                                    wf_idcs : Optional[List[int]] = None,
                                    wf_selector : Optional[Callable[..., bool]] = None,
                                    **kwargs) -> WaveformAdcs:

        """
        If wf_idcs is None and wf_selector is None,
        then this method creates a WaveformAdcs
        object whose Adcs attribute is the mean 
        of the adcs arrays for every waveform in 
        this WaveformSet. If wf_idcs is not None, 
        then such mean is computed using the adcs
        arrays of the waveforms whose iterator 
        values, with respect to this WaveformSet, 
        are given in wf_idcs. If wf_idcs is None 
        but wf_selector is not None, then such 
        mean is computed using the adcs arrays
        of the waveforms, wf, within this 
        WaveformSet for which 
        wf_selector(wf, *args, **kwargs) evaluates 
        to True. In any case, the TimeStep_ns
        attribute of the newly created WaveformAdcs
        object assumed to match that of the first
        waveform which was used in the average sum.
        
        In any case, the resulting WaveformAdcs
        object is assigned to the
        self.__mean_adcs attribute. The 
        self.__mean_adcs_idcs attribute is also
        updated with a tuple of the indices of the
        waveforms which were used to compute the
        mean WaveformAdcs. Finally, this method 
        returns the averaged WaveformAdcs object.

        Parameters
        ----------
        *args
            These arguments only make a difference if
            the 'wf_idcs' parameter is None and the
            'wf_selector' parameter is suitable defined.
            For each waveform, wf, these are the 
            positional arguments which are given to
            wf_selector(wf, *args, **kwargs) as *args.
        wf_idcs : list of int
            If it is not None, then it must be a list
            of integers which must be a valid iterator
            value for the __waveforms attribute of this
            WaveformSet. I.e. any integer i within such
            list must satisfy
            0 <= i <= len(self.__waveforms) - 1. Any
            integer which does not satisfy this condition
            is ignored. These integers give the waveforms
            which are averaged.
        wf_selector : callable 
            This parameter only makes a difference if 
            the 'wf_idcs' parameter is None. If that's 
            the case, and 'wf_selector' is not None, then 
            it must be a callable whose first parameter 
            must be called 'waveform' and its type 
            annotation must match the Waveform class. 
            Its return value must be annotated as a 
            boolean. In this case, the mean waveform 
            is averaged over those waveforms, wf, for 
            which wf_selector(wf, *args, **kwargs) 
            evaluates to True.
        *kwargs
            These keyword arguments only make a 
            difference if the 'wf_idcs' parameter is 
            None and the 'wf_selector' parameter is 
            suitable defined. For each waveform, wf, 
            these are the keyword arguments which are 
            given to wf_selector(wf, *args, **kwargs) 
            as **kwargs.

        Returns
        ----------
        output : np.ndarray
            The averaged adcs array
        """

        if len(self.__waveforms) == 0:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.compute_mean_waveform()',
                                                        'There are no waveforms in this WaveformSet object.'))
        if wf_idcs is None and wf_selector is None:

            output = self.__compute_mean_waveform_of_every_waveform()   # Average over every 
                                                                        # waveform in this WaveformSet
        elif wf_idcs is None and wf_selector is not None:

            signature = inspect.signature(wf_selector)

            if list(signature.parameters.keys())[0] != 'waveform':
                raise Exception(generate_exception_message( 2,
                                                            "WaveformSet.compute_mean_waveform()",
                                                            "The name of the first parameter of the given waveform-selector method must be 'waveform'."))
            
            if signature.parameters['waveform'].annotation != Waveform:
                raise Exception(generate_exception_message( 3,
                                                            "WaveformSet.compute_mean_waveform()",
                                                            "The 'waveform' parameter of the waveform-selector method must be hinted as a Waveform object."))
            if signature.return_annotation != bool:
                raise Exception(generate_exception_message( 4,
                                                            "WaveformSet.compute_mean_waveform()",
                                                            "The return type of the waveform-selector method must be hinted as a boolean."))

            output = self.__compute_mean_waveform_with_selector(wf_selector,
                                                                *args,
                                                                **kwargs)
        else:

            fWfIdcsIsWellFormed = False
            for idx in wf_idcs:
                if self.is_valid_iterator_value(idx):

                    fWfIdcsIsWellFormed = True
                    break                       # Just make sure that there 
                                                # is at least one valid 
                                                # iterator value in the given list

            if not fWfIdcsIsWellFormed:
                raise Exception(generate_exception_message( 5,
                                                            'WaveformSet.compute_mean_waveform()',
                                                            'The given list of waveform indices is empty or it does not contain even one valid iterator value in the given list. I.e. there are no waveforms to average.'))

            output = self.__compute_mean_waveform_of_given_waveforms(wf_idcs)   ## In this case we also need to remove indices
                                                                                ## redundancy (if any) before giving wf_idcs to
                                                                                ## WaveformSet.__compute_mean_waveform_of_given_waveforms.
                                                                                ## This is a open issue for now.
        return output
    
    def __compute_mean_waveform_of_every_waveform(self) -> WaveformAdcs:
        
        """
        This method should only be called by the
        WaveformSet.compute_mean_waveform() method,
        where any necessary well-formedness checks 
        have already been performed. It is called by 
        such method in the case where both the 'wf_idcs' 
        and the 'wf_selector' input parameters are 
        None. This method sets the self.__mean_adcs
        and self.__mean_adcs_idcs attributes according
        to the WaveformSet.compute_mean_waveform()
        method documentation. It also returns the 
        averaged WaveformAdcs object. Refer to the 
        WaveformSet.compute_mean_waveform() method 
        documentation for more information.

        Returns
        ----------
        output : np.ndarray
            The averaged adcs array
        """

        aux = self.Waveforms[0].Adcs                # WaveformSet.compute_mean_waveform() 
                                                    # has already checked that there is at 
                                                    # least one waveform in this WaveformSet
        for i in range(1, len(self.__waveforms)):
            aux += self.Waveforms[i].Adcs

        output = WaveformAdcs(  self.__waveforms[0].TimeStep_ns,
                                aux/len(self.__waveforms))
        
        self.__mean_adcs = output
        self.__mean_adcs_idcs = tuple(range(len(self.__waveforms)))

        return output
    
    def __compute_mean_waveform_with_selector(self, wf_selector : Callable[..., bool],
                                                    *args,
                                                    **kwargs) -> WaveformAdcs:
        
        """
        This method should only be called by the
        WaveformSet.compute_mean_waveform() method,
        where any necessary well-formedness checks 
        have already been performed. It is called by 
        such method in the case where the 'wf_idcs'
        parameter is None and the 'wf_selector' 
        parameter is suitably defined. This method 
        sets the self.__mean_adcs and 
        self.__mean_adcs_idcs attributes according
        to the WaveformSet.compute_mean_waveform()
        method documentation. It also returns the 
        averaged WaveformAdcs object. Refer to the 
        WaveformSet.compute_mean_waveform() method 
        documentation for more information.

        Parameters
        ----------
        wf_selector : callable
        *args
        **kwargs

        Returns
        ----------
        output : np.ndarray
            The averaged adcs array
        """

        added_wvfs = []

        aux = np.zeros((self.__points_per_wf,))

        for i in range(len(self.__waveforms)):
            if wf_selector(self.__waveforms[i], *args, **kwargs):
                aux += self.__waveforms[i].Adcs
                added_wvfs.append(i)
                
        if len(added_wvfs) == 0:
            raise Exception(generate_exception_message( 1,
                                                        'WaveformSet.__compute_mean_waveform_with_selector()',
                                                        'No waveform in this WaveformSet object passed the given selector.'))
    
        output = WaveformAdcs(  self.__waveforms[added_wvfs[0]].TimeStep_ns,
                                aux/len(added_wvfs))
        
        self.__mean_adcs = output
        self.__mean_adcs_idcs = tuple(added_wvfs)

        return output
    
    def __compute_mean_waveform_of_given_waveforms(self, wf_idcs : List[int]) -> WaveformAdcs:
        
        """
        This method should only be called by the
        WaveformSet.compute_mean_waveform() method,
        where any necessary well-formedness checks 
        have already been performed. It is called by 
        such method in the case where the 'wf_idcs'
        parameter is not None, regardless the input
        given to the 'wf_selector' parameter. This 
        method sets the self.__mean_adcs and 
        self.__mean_adcs_idcs attributes according
        to the WaveformSet.compute_mean_waveform()
        method documentation. It also returns the 
        averaged WaveformAdcs object. Refer to the 
        WaveformSet.compute_mean_waveform() method 
        documentation for more information.

        Parameters
        ----------
        wf_idcs : list of int

        Returns
        ----------
        output : np.ndarray
            The averaged adcs array
        """

        added_wvfs = []

        aux = np.zeros((self.__points_per_wf,))

        for idx in wf_idcs:
            try:                # WaveformSet.compute_mean_waveform() only checked that there 
                                # is at least one valid iterator value, but we need to handle
                                # the case where there are invalid iterator values

                aux += self.__waveforms[idx].Adcs
            except IndexError:
                continue        # Ignore the invalid iterator values as specified in the 
                                # WaveformSet.compute_mean_waveform() method documentation
            else:
                added_wvfs.append(idx)

        output = WaveformAdcs(  self.__waveforms[added_wvfs[0]].TimeStep_ns,
                                aux/len(added_wvfs))                            # len(added_wvfs) must be at least 1. 
                                                                                # This was already checked by 
                                                                                # WaveformSet.compute_mean_waveform()
        self.__mean_adcs = output
        self.__mean_adcs_idcs = tuple(added_wvfs)

        return output

    def is_valid_iterator_value(self, iterator_value : int) -> bool:

        """
        This method returns True if
        0 <= iterator_value <= len(self.__waveforms) - 1,
        and False if else.
        """

        if iterator_value < 0:
            return False
        elif iterator_value <= len(self.__waveforms) - 1:
            return True
        else:
            return False