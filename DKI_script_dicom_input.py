import os
import subprocess
import nibabel as nib
import numpy as np

from dipy.io import read_bvals_bvecs
from dipy.core.gradients import gradient_table
from dipy.segment.mask import median_otsu
from dipy.reconst.dki import DiffusionKurtosisModel

def main():
    # -------------------------------------------------------------------------
    # SETTINGS & PATHS
    # -------------------------------------------------------------------------
    # Processed file paths (if these exist, conversion will be skipped)
    processed_nii_file  = r"D:\Research\NODDI_test\NODDI_TEST2\Processed\myDTI.nii.gz"
    processed_bval_file = r"D:\Research\NODDI_test\NODDI_TEST2\Processed\myDTI.bval"
    processed_bvec_file = r"D:\Research\NODDI_test\NODDI_TEST2\Processed\myDTI.bvec"
    
    # DICOM input folder (used if processed files are not found)
    dicom_dir = r"D:\Research\NODDI_test\NODDI_TEST2\ejemplo_NODDI_ALD\tempALD\20241113\601_DTI_NODDI_EPICorr"
    
    # Temporary output folder for conversion (if needed)
    dcm2niix_outdir = r"D:\Research\NODDI_test\NODDI_TEST2\ConvertedNIfTI"
    base_name = "myDTI"  # Base filename for conversion
    
    # Final output directory for DKI maps
    dki_outdir = r"D:\Research\NODDI_test\DKI\DKI_output"
    os.makedirs(dki_outdir, exist_ok=True)
    
    # -------------------------------------------------------------------------
    # STEP 1: CHECK IF PROCESSED NIfTI EXISTS; IF NOT, PERFORM CONVERSION
    # -------------------------------------------------------------------------
    if os.path.exists(processed_nii_file) and os.path.exists(processed_bval_file) and os.path.exists(processed_bvec_file):
        print("Found processed NIfTI files. Skipping DICOM conversion.")
        nii_file  = processed_nii_file
        bval_file = processed_bval_file
        bvec_file = processed_bvec_file
    else:
        print("Processed NIfTI not found. Converting DICOM to NIfTI with dcm2niix...")
        os.makedirs(dcm2niix_outdir, exist_ok=True)
        subprocess.run([
            "dcm2niix",
            "-o", dcm2niix_outdir,
            "-f", base_name,
            "-z", "y",  # Force .nii.gz output
            dicom_dir
        ], check=True)
        nii_file  = os.path.join(dcm2niix_outdir, base_name + ".nii.gz")
        bval_file = os.path.join(dcm2niix_outdir, base_name + ".bval")
        bvec_file = os.path.join(dcm2niix_outdir, base_name + ".bvec")
    
    # -------------------------------------------------------------------------
    # STEP 2: LOAD DIFFUSION DATA AND GRADIENT INFORMATION
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
    # Identify b0 indices (typically, b-values < 50 are considered b0)
    b0_indices = np.where(bvals < 50)[0]
    if len(b0_indices) == 0:
        b0_indices = [0]  # Fallback: use the first volume if no b0 is found
    print("Using b0 indices for masking:", b0_indices)

    print("Generating brain mask with median_otsu...")
    masked_data, mask = median_otsu(data, vol_idx=b0_indices, median_radius=4, numpass=2)
    
    # -------------------------------------------------------------------------
    # STEP 4: FIT THE DIFFUSION KURTOSIS MODEL (DKI)
    # -------------------------------------------------------------------------
    print("Fitting DKI model...")
    dki_model = DiffusionKurtosisModel(gtab, fit_method='WLS')
    dki_fit = dki_model.fit(masked_data, mask=mask)
    
    # Extract parametric maps:
    MK = dki_fit.mk()   # Mean Kurtosis
    AK = dki_fit.ak()   # Axial Kurtosis
    RK = dki_fit.rk()   # Radial Kurtosis
    FA = dki_fit.fa     # Fractional Anisotropy
    MD = dki_fit.md     # Mean Diffusivity (accessed as an attribute)

    # -------------------------------------------------------------------------
    # STEP 5: SAVE THE DKI MAPS
    # -------------------------------------------------------------------------
    nib.save(nib.Nifti1Image(MK.astype(np.float32), affine), os.path.join(dki_outdir, "MK.nii.gz"))
    nib.save(nib.Nifti1Image(AK.astype(np.float32), affine), os.path.join(dki_outdir, "AK.nii.gz"))
    nib.save(nib.Nifti1Image(RK.astype(np.float32), affine), os.path.join(dki_outdir, "RK.nii.gz"))
    nib.save(nib.Nifti1Image(FA.astype(np.float32), affine), os.path.join(dki_outdir, "FA.nii.gz"))
    nib.save(nib.Nifti1Image(MD.astype(np.float32), affine), os.path.join(dki_outdir, "MD.nii.gz"))

    print("DKI fitting complete. Maps saved to:", dki_outdir)

if __name__ == "__main__":
    main()
