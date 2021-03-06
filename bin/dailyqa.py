import os
import glob
import numpy as np
import astropy.io.fits as fits

from astropy.table import Table, join
from desisurvey.utils import get_date
from get_solar import get_solar
from desitarget.sv1.sv1_targetmask import desi_mask as sv1_desi_mask
from desitarget.sv1.sv1_targetmask import bgs_mask as sv1_bgs_mask


cpath    = '/global/cfs/cdirs/desi/survey/observations/SV1/sv1-exposures.fits'
conds    = Table.read(cpath)
conds    = conds[conds['TARGETS'] == 'BGS+MWS']

bgs_dark = conds[conds['GFA_MOON_ZD_DEG'] > 90.0]
bgs_dark['PROD'] = 'blanc'
bgs_dark['PROD'][bgs_dark['NIGHT'].data.astype(np.int) > 20201223] = ''

# zbest-0-80623-deep.fits;
deep_ids = [x.split('/')[-2] for x in glob.glob('/global/homes/m/mjwilson/blanc/tiles/*/deep')]

def get_truth(tileid, petal, night, expid, verbose=False):
    if tileid in deep_ids:
        return  Table.read('/global/homes/m/mjwilson/blanc/tiles/{}/deep/zbest-{}-{}-deep.fits'.format(tileid, petal, tileid), 'ZBEST')

    elif tileid in bgs_dark['TILEID'].data:
        row = bgs_dark[bgs_dark['TILEID'].data == tileid]

        if len(row) > 1:
            if verbose:
                print('Found {} in bgs_dark for {} with exptimes {} on nights {} with spec. sky r {}'.format(row['EXPID'].data, tileid, ['{:.1f}'.format(x) for x in row['EXPTIME'].data],\
                                                                                                             row['NIGHT'].data, ['{:.1f}'.format(x) for x in row['SPECMODEL_SKY_RMAG_AB'].data]))


            i=0 
                
            while (row['EXPTIME'].data[i] < 300.) | (row['SPECMODEL_SKY_RMAG_AB'].data[i] <= 20.5):
                i += 1

            row = row[i]
            
        else:
            row = row[0]
            
        if row['PROD'] == 'blanc':
            try:
                path = '/global/cscratch1/sd/mjwilson/desi/SV1/spectra/exposures/NEXP1/{}/{}/coadd-{}-{}-{:08d}.fits'.format(tileid, night, night, petal, expid)
                
                # /global/cscratch1/sd/mjwilson/desi/SV1/spectra/exposures/NEXP1/80619/20201222/coadd-20201218-3-00068672.fits
                return  Table.read(path, 'ZBEST')

            except:
                print('Failed on {} in blanc production.'.format(path))
                
                return None

        else:
            try:
                # 80645/zbest-2-80645-00070961.fits
                path = '/global/cscratch1/sd/mjwilson/desi/SV1/spectra/daily/exposures/NEXP1/{}/zbest-{}-{}-{:08d}.fits'.format(tileid, petal, tileid, expid)
                return  Table.read(path, 'ZBEST')

            except:
                print('Failed on {} in daily production.'.format(path))
                return None

                
    else:
        print('No truth known for {}.'.format(tileid))
        return None
    
'''
# /global/cscratch1/sd/mjwilson/desi/SV1/spectra/exposures/NEXP1/80619/20201222/coadd-20201218-3-00068672.fits
files  = glob.glob('/global/cscratch1/sd/mjwilson/desi/SV1/spectra/exposures/NEXP1/*/*/coadd-*.fits')
zfiles = glob.glob('/global/cscratch1/sd/mjwilson/desi/SV1/spectra/exposures/NEXP1/*/*/zbest-*.fits')

tiles  = [os.path.dirname(x).split('/')[-2] for x in files]
expids = [os.path.basename(x).split('-')[-1].replace('.fits', '') for x in files]
'''   
                
files  = glob.glob('/global/cscratch1/sd/mjwilson/desi/SV1/spectra/daily/exposures/NEXP1/*/spectra-*.fits')
zfiles = glob.glob('/global/cscratch1/sd/mjwilson/desi/SV1/spectra/daily/exposures/NEXP1/*/zbest-*.fits')

tiles  = [os.path.dirname(x).split('/')[-1] for x in files]
expids = [os.path.basename(x).split('-')[-1].replace('.fits', '') for x in files]

utiles = np.unique(tiles)
uexps  = np.unique(expids)

print('Number of spectra files: {}'.format(len(files)))
print('Number of zbest files: {}'.format(len(zfiles)))
print('Number of exposures: {}'.format(len(uexps)))
print('Number of tiles: {}'.format(len(utiles)))
print('\n\n')


for f in zfiles:
    tileid = np.int(os.path.dirname(f).split('/')[-1])
    expid  = np.int(os.path.basename(f).split('-')[-1].replace('.fits', ''))  

    row = conds[conds['EXPID'].data.astype(np.int) == expid]

    petal = np.int(os.path.basename(f).split('-')[1])
    
    # /global/cscratch1/sd/mjwilson/desi/SV1/spectra/daily/exposures/NEXP1/80643/zbest-0-80643-00070736.fits
    f = fits.open(f)
    
    tids = np.unique(f[2].data['TILEID'])[0]
    expids = np.unique(f[2].data['EXPID'])[0] 

    mjds = np.unique(f[2].data['MJD'])
    dates = [get_date(x).isoformat() for x in mjds]
    
    assert (tids == tileid)
    assert (expids == expid)

    truth = get_truth(tileid, petal, dates[0], expid)

    if truth is None:
        continue

    truez = truth['TARGETID', 'DELTACHI2', 'Z', 'ZWARN']
    truez = truez[truez['ZWARN'] == 0]
    truez = truez[truez['DELTACHI2'] > 25.]
    truez = truez[(truez['Z'] > 0.01) & (truez['Z'] < 0.5)]
    truez['TRUEZ'] = truez['Z']

    if len(truez) == 0:
        print('Excluded {} truth'.format(tileid))
        continue
    
    del truez['Z']
    
    #
    ra = row['TILERA']
    dec= row['TILEDEC']

    solar = get_solar(mjds[0], ra, dec)
    
    zbest = f[1].data
    fmap = f[2].data

    assert  len(zbest) == 500
    
    bgs = (fmap['SV1_DESI_TARGET'] & sv1_desi_mask['BGS_ANY']) != 0
    bright = (fmap['SV1_BGS_TARGET']  & sv1_bgs_mask['BGS_BRIGHT']) != 0
    faint = (fmap['SV1_BGS_TARGET']  & sv1_bgs_mask['BGS_FAINT'])  != 0

    gaia_g = fmap['GAIA_PHOT_G_MEAN_MAG'].data
    rmag = 22.5 - 2.5 * np.log10(fmap['FLUX_R'].data)
    
    # Not in GAIA | (GAIA g - rmag > 0.6)
    # nonstar = (gaia_g == 0.0) | (gaia_g - rmag > 0.6)
    nonstar = np.ones_like(bgs).astype(bool)
    
    bgs = bgs & nonstar
    bright = bright & nonstar
    faint = faint & nonstar

    bgsids = fmap['TARGETID'][bgs]
    brightids = fmap['TARGETID'][bright]
    faintids = fmap['TARGETID'][faint]

    exit(0)
    
    # print(len(bgsids), len(brightids), len(faintids))
    
    #
    goodfiber = (zbest['ZWARN'] & 2**9) == 0

    # Assigned to a good fiber. 
    zbest = zbest[goodfiber]

    # Join with truth in the range of interest.
    zbest = join(zbest, truez['TARGETID', 'TRUEZ'], keys='TARGETID', join_type='left')

    # Limit to known zs in the range of interest on a working fiber.
    zbest = zbest[~zbest['TRUEZ'].mask]
    
    # Samples assigned to a good fiber. 
    bgs = zbest[np.isin(zbest['TARGETID'], bgsids)]
    bright = zbest[np.isin(zbest['TARGETID'], brightids)]
    faint = zbest[np.isin(zbest['TARGETID'], faintids)]

    bgs_goodz = bgs[(bgs['ZWARN'] == 0) & (bgs['DELTACHI2'] >= 25.) & (np.abs(bgs['Z'] - bgs['TRUEZ']) < 0.003335)]
    bright_goodz = bright[(bright['ZWARN'] == 0) & (bright['DELTACHI2'] >= 25.) & (np.abs(bright['Z'] - bright['TRUEZ']) < 0.003335)]
    faint_goodz = faint[(faint['ZWARN'] == 0) & (faint['DELTACHI2'] >= 25.) & (np.abs(faint['Z'] - faint['TRUEZ']) < 0.003335)]

    try:
        toprint = '{}\t\t{: 4.3f}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}\t\t{:.3f}\t{:.3f}\t{:.3f}\t{:.3f}\t\t{:.3f}\t{:.3f}\t{:.3f}'.format(dates[0], row['EXPTIME'][0], row['GFA_TRANSPARENCY'][0], row['GFA_FWHM_ASEC'][0],\
                                                                                                                                          row['B_DEPTH'][0], row['R_DEPTH'][0], row['Z_DEPTH'][0],\
                                                                                                                                          solar['AIRMASS'][0], solar['MOONALT'][0], solar['MOONSEP'][0], solar['MOONFRAC'][0],\
                                                                                                                                          100. * len(bgs_goodz) / len(bgs), 100. * len(bright_goodz) / len(bright),\
                                                                                                                                          100. * len(faint_goodz) / len(faint))

        toprint += '\t\t{:d}\t{:d}\t{:d}'.format(len(bgs_goodz), len(bright_goodz), len(faint_goodz))

        print(toprint)
        
    except:
        print('Failed on {}'.format(expid))

print('\n\nDone.\n\n')
