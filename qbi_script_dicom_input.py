import os
import subprocess
import nibabel as nib
import numpy as np

from dipy.io import read_bvals_bvecs
from dipy.core.gradients import gradient_table
from dipy.segment.mask import median_otsu
from dipy.reconst.shm import CsaOdfModel
from dipy.data import get_sphere

def main():
    # -------------------------------------------------------------------------
    # SETTINGS: Set to True if you already have processed NIfTI data.
    # -------------------------------------------------------------------------
    already_processed = True  # Set to False if you need to convert from DICOM.

    # -------------------------------------------------------------------------
    # DEFINE PATHS
    # -------------------------------------------------------------------------
    # If already processed, specify the processed NIfTI and associated files.
    processed_nii_file  = r"D:\Research\NODDI_test\NODDI_TEST2\Processed\myDTI.nii.gz"
    processed_bval_file = r"D:\Research\NODDI_test\NODDI_TEST2\Processed\myDTI.bval"
    processed_bvec_file = r"D:\Research\NODDI_test\NODDI_TEST2\Processed\myDTI.bvec"
    
    # If not processed, specify the DICOM input folder and conversion output directory.
    dicom_dir       = r"D:\Research\NODDI_test\NODDI_TEST2\ejemplo_NODDI_ALD\tempALD\20241113\601_DTI_NODDI_EPICorr"
    dcm2niix_outdir = r"D:\Research\NODDI_test\NODDI_TEST2\ConvertedNIfTI"
    base_name       = "myDTI"  # Base filename for conversion.
    
    # Final output directory for Q-Ball results.
    qball_outdir = r"D:\Research\NODDI_test\NODDI_TEST2\QBI_output"
    os.makedirs(qball_outdir, exist_ok=True)

    # -------------------------------------------------------------------------
    # STEP 1: CONVERT DICOM TO NIfTI (if not already processed)
    # -------------------------------------------------------------------------
    if not already_processed:
        os.makedirs(dcm2niix_outdir, exist_ok=True)
        print("Converting DICOM to NIfTI with dcm2niix...")
        subprocess.run([
            "dcm2niix",
            "-o", dcm2niix_outdir,
            "-f", base_name,
            "-z", "y",  # force .nii.gz output
            dicom_dir
        ], check=True)
        nii_file   = os.path.join(dcm2niix_outdir, base_name + ".nii.gz")
        bval_file  = os.path.join(dcm2niix_outdir, base_name + ".bval")
        bvec_file  = os.path.join(dcm2niix_outdir, base_name + ".bvec")
    else:
        nii_file   = processed_nii_file
        bval_file  = processed_bval_file
        bvec_file  = processed_bvec_file

    # -------------------------------------------------------------------------
    # STEP 2: LOAD THE DIFFUSION DATA
    # -------------------------------------------------------------------------
    print("Loading NIfTI and gradient files...")
    img = nib.load(nii_file)
    data = img.get_fdata()
    affine = img.affine

    bvals, bvecs = read_bvals_bvecs(bval_file, bvec_file)
    gtab = gradient_table(bvals, bvecs=bvecs)

    # -------------------------------------------------------------------------
    # STEP 3: CREATE A BRAIN MASK USING b0 VOLUMES
    # -------------------------------------------------------------------------
    # Identify b0 indices (typically b-values below 50)
    b0_indices = np.where(bvals < 50)[0]
    if len(b0_indices) == 0:
        b0_indices = [0]  # fallback: use the first volume if no b0 is found
    print("Using b0 indices for masking:", b0_indices)

    print("Generating a brain mask using median_otsu...")
    # Provide vol_idx to median_otsu so it uses the appropriate volumes.
    masked_data, mask = median_otsu(data, vol_idx=b0_indices, median_radius=4, numpass=2)

    # -------------------------------------------------------------------------
    # STEP 4: FIT THE Q-BALL MODEL (CSA ODF MODEL)
    # -------------------------------------------------------------------------
    print("Fitting Q-Ball model (CSA)...")
    csa_model = CsaOdfModel(gtab, sh_order=6)
    csa_fit = csa_model.fit(masked_data, mask=mask)

    # Compute the Generalized Fractional Anisotropy (GFA)
    gfa = csa_fit.gfa

    # -------------------------------------------------------------------------
    # STEP 5: SAVE THE GFA MAP
    # -------------------------------------------------------------------------
    gfa_img = nib.Nifti1Image(gfa.astype(np.float32), affine)
    gfa_file = os.path.join(qball_outdir, "QBI_GFA.nii.gz")
    nib.save(gfa_img, gfa_file)

    print(f"Q-Ball imaging complete.\nGFA map saved to: {gfa_file}")

if __name__ == "__main__":
    main()
