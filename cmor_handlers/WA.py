import os, sys
import traceback
import cmor
import cdms2


#
#  PARTIAL
#


def handle(infile="", tables_dir=""):
    """
    Transform E3SM.FLDS into CMIP.hfls
    float WA(time, lat, lon) ;
		WA:long_name = "water in the unconfined aquifer (vegetated landunits only)" ;
		WA:units = "mm" ;
		WA:cell_methods = "time: mean" ;
		WA:_FillValue = 1.e+36f ;
		WA:missing_value = 1.e+36f ;
		WA:cell_measures = "area: area" ;
    """
    if not infile:
        return "hello from {}".format(__name__)
    # extract data from the input file
    f = cdms2.open(infile)
    data = f('EFLX_LH_TOT')
    lat = data.getLatitude()[:]
    lon = data.getLongitude()[:]
    lat_bnds = f('lat_bnds')
    lon_bnds = f('lon_bnds')
    time = data.getTime()
    time_bnds = f('time_bounds')
    f.close()

    # setup cmor
    tables_path = os.path.join(tables_dir, 'Tables')
    test_path = os.path.join(tables_dir, 'Test', 'common_user_input.json')
    cmor.setup(inpath=tables_path, netcdf_file_action=cmor.CMOR_REPLACE)
    cmor.dataset_json(test_path)
    table = 'CMIP6_Amon.json'
    cmor.load_table(table)

    # create axes
    axes = [{
        'table_entry': 'time',
        'units': time.units
    }, {
        'table_entry': 'latitude',
        'units': 'degrees_north',
        'coord_vals': lat[:],
        'cell_bounds': lat_bnds[:]
    }, {
        'table_entry': 'longitude',
        'units': 'degrees_east',
        'coord_vals': lon[:],
        'cell_bounds': lon_bnds[:]
    }]
    axis_ids = list()
    for axis in axes:
        axis_id = cmor.axis(**axis)
        axis_ids.append(axis_id)

    # create the cmor variable
    varid = cmor.variable('hfls', 'W/m^2', axis_ids, positive='up')

    # write out the data
    try:
        for index, val in enumerate(data.getTime()[:]):
            cmor.write(varid, data[index, :], time_vals=val, time_bnds=[time_bnds[index, :]])
    except:
        raise
    finally:
        cmor.close(varid)