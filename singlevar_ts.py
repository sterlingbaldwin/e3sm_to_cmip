import os, sys
import argparse
import cdms2
from random import uniform
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from subprocess import Popen, PIPE
from time import sleep

import logging
import traceback

def split(var_list, caseid, inpath, outpath, start, end, nproc, proc_vars=False, data_type='clm2.h0'):
    """
    Extract all variables in var_list from all files
    found in inpath that match the caseid and are between 
    in the years start-end inclusive
    """
    prev_dir = os.getcwd()
    outpath = os.path.abspath(outpath)
    os.chdir(os.path.abspath(inpath))

    from imp import reload
    reload(logging)
    logging.basicConfig(
        format='%(asctime)s:%(levelname)s: %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        filename=os.path.join(prev_dir, 'splitter.log'),
        filemode='w',
        level=logging.DEBUG)
    msg = 'starting splitter'
    logging.info(msg)
    msg = '''
        var_list: {vars}
        caseid: {caseid}
        inpath: {input}
        outpath: {out}
        start-year: {start}
        end-year: {end}
        nproc: {nproc}'''.format(
            vars=var_list,
            caseid=caseid,
            input=inpath,
            out=outpath,
            start=start,
            end=end,
            nproc=nproc)
    logging.info(msg)

    # First get the list of files in our year range that match the caseid
    contents = os.listdir(os.getcwd())
    files = list()
    start_pattern = '{caseid}.{type}.'.format(
        caseid=caseid,
        type=data_type)
    start_pattern_len = len(start_pattern)
    end_pattern = '.nc'
    end_pattern_len = 3
    for item in contents:
        index = item.find(start_pattern)
        if index is None:
            continue
        end_index = item.find(end_pattern)
        if end_index is None:
            continue
        try:
            year = int(item[index + start_pattern_len: end_index - end_pattern_len])
        except:
            continue
        if year >= start and year <= end:
            files.append(item)
    msg = 'found {} input files'.format(len(files))
    logging.info(msg)

    # Second if the var_list is set to 'all' open up one of the input files
    # and grab a list of all variables
    if var_list[0] == 'all':
        msg = 'splitting all variables'
        logging.info(msg)
        print msg
        var_list = list()
        f = cdms2.open(files[0])
        for key, _ in f.variables.items():
            if key[0].isupper():
                var_list.append(key)

    msg = 'found {} variables to extract'.format(len(var_list))
    logging.info(msg)
    print msg
    for var in var_list:
        logging.info(var)
    # Finally create a process pool of all the selected variables
    # and extract them into the output dir
    if proc_vars:
        len_vars = len(var_list)
        ncpu = cpu_count()
        if len_vars >= 100:
            nproc = 100 if ncpu > 100 else ncpu - 1
        else:
            nproc = len_vars

    nproc = len(var_list) if nproc > len(var_list) else nproc
    msg = 'starting extraction with nproc = {}'.format(nproc)
    logging.info(msg)
    print msg
    pool_res = list()
    pool = ThreadPool(nproc)
    for var in var_list:
        outfile = os.path.join(
            outpath,'{caseid}.{var}.nc'.format(
                caseid=caseid, var=var))
        pool_res.append(pool.apply_async(split_one, [var, files, outfile]))

    for res in pool_res:
        out, err = res.get()
        if out: print out
        if err: print out, err
    pool.close()
    pool.join()
    os.chdir(prev_dir)

def split_one(var, infiles, outfile):
    """
    Split a single variable from a list of files into the outfile
    """
    cmd = ['ncrcat', '-O', '-cv', var] + infiles + [outfile]
    msg = 'starting {}'.format(var)
    logging.info(msg)
    while True:
        try:
            proc = Popen(cmd, stderr=PIPE, stdout=PIPE)
            out, err = proc.communicate()
        except Exception as e:
            msg = format_debug(e)
            logging.error(e)
            sleep(uniform(0.1, 0.5))
        else:
            break
    msg = 'finished {}'.format(var)
    logging.info(msg)
    return out, err

def format_debug(e):
    """
    Return a string of an exceptions relavent information
    """
    _, _, tb = sys.exc_info()
    return """
1: {doc}
2: {exec_info}
3: {exec_0}
4: {exec_1}
5: {lineno}
6: {stack}
""".format(
    doc=e.__doc__,
    exec_info=sys.exc_info(),
    exec_0=sys.exc_info()[0],
    exec_1=sys.exc_info()[1],
    lineno=traceback.tb_lineno(sys.exc_info()[2]),
    stack=traceback.print_tb(tb))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-v', '--var-list',
        nargs='+',
        help='space sepperated list of variables, use \'all\' to extract all variables')
    parser.add_argument(
        '-c', '--case-id',
        help='name of case, e.g. 20180129.DECKv1b_piControl.ne30_oEC.edison',
        required=True)
    parser.add_argument(
        '-i', '--input-path',
        help='path to input directory',
        required=True)
    parser.add_argument(
        '-o', '--output-path',
        help='path to output directory',
        required=True)
    parser.add_argument(
        '-s', '--start-year',
        help='first year to extract',
        type=int,
        required=True)
    parser.add_argument(
        '-e', '--end-year',
        help='last year to split',
        type=int,
        required=True)
    parser.add_argument(
        '-n', '--num-proc',
        help='number of parallel processes, default = 6',
        type=int, default=6)
    parser.add_argument(
        '-N', '--proc-vars',
        action='store_true',
        help='set the number of process to the number of variables')
    parser.add_argument(
        '-d', '--data-type',
        required=True,
        default='cam.h0',
        help='The type of data to extract from, e.g. clm2.h0 or cam.h0. Defaults to cam.h0')
    try:
        args = parser.parse_args(sys.argv[1:])
    except:
        parser.print_help()
        sys.exit(1)
    
    if args.var_list:
        var_list = args.var_list
    else:
        if args.data_type == 'clm2.h0':
            var_list = ['FLDS', 'QSOIL', 'WA', 'FROST_TABLE', 'SNOW_DEPTH',
                        'FSDSNI', 'FH2OSFC', 'FSNO', 'FGR', 'QBOT', 'SNOW_SOURCES',
                        'TSOI', 'TBOT', 'EFLX_LH_TOT', 'TLAI', 'FSDS', 'FSDSVI',
                        'Q2M', 'TSA', 'QCHARGE', 'ZWT', 'FCEV', 'SNOWDP', 'FIRE',
                        'QVEGT', 'SOILLIQ', 'SOILICE', 'QDRAI', 'FCOV', 'ESAI',
                        'FPSN', 'SNOWICE', 'WIND', 'FSA', 'QVEGE', 'FSH', 'H2OSFC',
                        'FSM', 'FSR', 'TLAKE', 'BTRAN', 'SNOWLIQ', 'QSNOMELT', 'FSDSVD',
                        'FSDSND', 'FCTR', 'QRUNOFF', 'TSAI', 'FGEV', 'ELAI', 'ZWT_PERCH',
                        'TWS', 'H2OSOI', 'PBOT', 'TV', 'QOVER', 'SNOW_SINKS', 'QRGWL',
                        'TG', 'FIRA', 'RAIN', 'FSAT', 'VOLR', 'H2OSNO', 'RH2M','SNOW',
                        'FGR12']
        elif args.data_type == 'cam.h0':
            var_list = ['FSNTOA', 'FLUT', 'FSNT', 'FLNT', 'FSNS', 'FLNS', 'SHFLX', 'QFLX', 
                        'PRECC', 'PRECL', 'PRECSC', 'PRECSL', 'TS', 'TREFHT']

    split(var_list=var_list,
          inpath=args.input_path,
          caseid=args.case_id,
          outpath=args.output_path,
          start=args.start_year,
          end=args.end_year,
          nproc=args.num_proc,
          proc_vars=args.proc_vars,
          data_type=args.data_type)
