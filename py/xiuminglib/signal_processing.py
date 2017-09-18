"""
Functions for Signal Processing Techniques

Xiuming Zhang, MIT CSAIL
August 2017
"""

import logging
from os.path import abspath
import numpy as np
from scipy.sparse import issparse
from scipy.sparse.linalg import eigsh
from scipy.special import sph_harm
import logging_colorer # noqa: F401 # pylint: disable=unused-import

logging.basicConfig(level=logging.INFO)
thisfile = abspath(__file__)


def pca(data_mat, n_pcs=None, eig_method='scipy.sparse.linalg.eigsh'):
    """
    Perform PCA on data via eigendecomposition of covariance matrix
        To reconstruct data with top k PC's, do
            pcs[:, :k].dot(projs[:k, :]) + np.tile(data_mean, (projs.shape[1], 1)).T

    Args:
        data_mat: Data matrix of n data points in the m-D space
            Array_like, dense or sparse, of shape (m, n); each column is a point
        n_pcs: Number of top PC's requested
            Positive integer < m
            Optional; defaults to m - 1
        eig_method: Method for eigendecomposition of the symmetric covariance matrix
            'numpy.linalg.eigh' or 'scipy.sparse.linalg.eigsh'
            Optional; defaults to 'scipy.sparse.linalg.eigsh'

    Returns:
        pcvars: PC variances (eigenvalues of covariance matrix) in descending order
            Numpy array of length n_pcs
        pcs: Corresponding PC's (normalized eigenvectors)
            Numpy array of shape (m, n_pcs); each column is a PC
        projs: Data points centered and then projected to the n_pcs-D PC space
            Numpy array of shape (n_pcs, n); each column is a point
        data_mean: Mean that can be used to recover raw data
            Numpy array of length m
    """
    if issparse(data_mat):
        data_mat = data_mat.toarray()
    else:
        data_mat = np.array(data_mat)
    # data_mat is NOT centered

    if n_pcs is None:
        n_pcs = data_mat.shape[0] - 1

    # ------ Compute covariance matrix of data

    covmat = np.cov(data_mat) # auto handles uncentered data
    # covmat is real and symmetric in theory, but may not be so due to numerical issues,
    # so eigendecomposition method should be told explicitly to exploit symmetry constraints

    # ------ Compute eigenvalues and eigenvectors

    if eig_method == 'scipy.sparse.linalg.eigsh':
        # Largest (in magnitude) n_pcs eigenvalues
        eig_vals, eig_vecs = eigsh(covmat, k=n_pcs, which='LM')
        # eig_vals in ascending order
        # eig_vecs columns are normalized eigenvectors

        pcvars = eig_vals[::-1] # descending
        pcs = eig_vecs[:, ::-1]

    elif eig_method == 'numpy.linalg.eigh':
        # eigh() prevents complex eigenvalues, compared with eig()
        eig_vals, eig_vecs = np.linalg.eigh(covmat)
        # eig_vals in ascending order
        # eig_vecs columns are normalized eigenvectors

        # FIXME -- sometimes the eigenvalues are not sorted? Subnormals appear. All zero eigenvectors
        sort_ind = eig_vals.argsort() # ascending
        eig_vals = eig_vals[sort_ind]
        eig_vecs = eig_vecs[:, sort_ind]

        pcvars = eig_vals[:-(n_pcs + 1):-1] # descending
        pcs = eig_vecs[:, :-(n_pcs + 1):-1]

    else:
        raise NotImplementedError(eig_method)

    # ------ Center and then project data points to PC space

    data_mean = np.mean(data_mat, axis=1)
    data_mat_centered = data_mat - np.tile(data_mean.reshape(-1, 1), (1, data_mat.shape[1]))
    projs = np.dot(pcs.T, data_mat_centered)

    return pcvars, pcs, projs, data_mean


def matrix_for_real_spherical_harmonics(l, n_theta):
    """
    Generate transform matrix for discrete real spherical harmonic expansion

    Theta-phi convention (here) / latitude-longitude convention
                                                       ^ z (theta = 0 / lat = 90)
                                                       |
                                                       |
                      (phi = 270 / lng = -90) ---------+---------> y (phi = 90 / lng = 90)
                                                     ,'|
                                                   ,'  |
        (theta = 90, phi = 0 / lat = 0, lng = 0) x     | (theta = 180 / lat = -90)

    Args:
        l: Up to which band (starting form 0); the number of harmonics is (l + 1) ** 2;
            in other words, all harmonics within each band (-l <= m <= l) are used
            Natural number
        n_theta: Number of discretization levels of polar angle, 0 =< theta < 180; with the
            same step size, n_phi will be twice as big, since 0 =< phi < 360
            Natural number

    Returns:
        ymat: Transform matrix whose row i, when dotting with flattened image vector, gives the
            coefficient for i-th harmonic, where i = (l + 1) * l + m; the spherical function to
            transform (in the form of 2D image indexed by theta and phi) should be flattened in
            row-major order: the row index varies the slowest, and the column index the quickest
            Numpy array of shape ((l + 1) ** 2, 2 * n_theta ** 2)
    """
    n_phi = 2 * n_theta

    # Generate the l and m values for each matrix location
    l_mat = np.zeros(((l + 1) ** 2, n_theta * n_phi))
    m_mat = np.zeros(l_mat.shape)
    i = 0
    for curr_l in range(l + 1):
        for curr_m in range(-curr_l, curr_l + 1):
            l_mat[i, :] = curr_l * np.ones(l_mat.shape[1])
            m_mat[i, :] = curr_m * np.ones(l_mat.shape[1])
            i += 1

    # Generate the theta and phi values for each matrix location
    step_size = np.pi / n_theta
    phis, thetas = np.meshgrid(np.linspace(0 + step_size, 2 * np.pi - step_size, num=n_phi, endpoint=True),
                               np.linspace(0 + step_size, np.pi - step_size, num=n_theta, endpoint=True))
    theta_mat = np.tile(thetas.ravel(), (l_mat.shape[0], 1))
    phi_mat = np.tile(phis.ravel(), (l_mat.shape[0], 1))

    # Evaluate (complex) spherical harmonics at these locations
    ymat_complex = sph_harm(m_mat, l_mat, phi_mat, theta_mat)

    # Derive real spherical harmonics
    ymat_complex_real = np.real(ymat_complex)
    ymat_complex_imag = np.imag(ymat_complex)
    ymat = np.zeros(ymat_complex_real.shape)
    ind = m_mat > 0
    ymat[ind] = np.sqrt(2) * ymat_complex_real[ind]
    ind = m_mat == 0
    ymat[ind] = ymat_complex_real[ind]
    ind = m_mat < 0
    ymat[ind] = np.sqrt(2) * ymat_complex_imag[ind]

    return ymat