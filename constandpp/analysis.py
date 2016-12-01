#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Collection of functions involved in analyzing the data that was processed by dataproc.py and constand.py.
Performs a differential expression analysis on the normalized intensities as provided by CONSTANd.
"""

import numpy as np
import pandas as pd
from warnings import warn
from collections import defaultdict
from statsmodels.sandbox.stats.multicomp import multipletests
from scipy.stats import ttest_ind as ttest
from sklearn.decomposition import PCA
from scipy.cluster.hierarchy import linkage, dendrogram
from matplotlib import pyplot as plt


def getRTIsolationInfo(removedData_RT):
	"""
	Returns dataFrame with the mean, standard deviation, and max-min value of the RT values for each duplicate_group
	representative that is found in the removedData_RT dataframe containing the removedData for the RT collapse.
	:param removedData_RT:  pd.dataFrame    removedData for the RT collapse.
	:return:                pd.DataFrame    statistics 'Degeneracy', 'mean', 'std', 'max-min' about the RT values
	"""
	duplicateGroups = removedData_RT.groupby('Representative First Scan').groups
	RTIsolationInfo = []
	for rfs, duplicates in duplicateGroups.items():
		RTValues = removedData_RT.loc[duplicates, 'RT [min]']
		RTIsolationInfo.append([rfs, len(duplicates), np.nanmean(RTValues), np.std(RTValues), np.ptp(RTValues)])
	return pd.DataFrame(RTIsolationInfo, columns=['Representative First Scan', 'Degeneracy', 'mean', 'std', 'max-min'])


def getNoIsotopicCorrection(df, noCorrectionIndices):
	"""
	Given a dataframe and indices of detections that received no corrections, returns some basic info about them.
	:param df:                  pd.dataFrame
	:param noCorrectionIndices: list            indices of detections that received no isotopic correction
	:return:                    pd.dataFrame    ['First Scan', 'Identifying Node', 'Annotated Sequence', 'Master Protein Accessions']
	"""
	return df.loc[noCorrectionIndices, ['First Scan', 'Identifying Node', 'Annotated Sequence', 'Master Protein Accessions']]


def getProteinPeptidesDicts(df):
	"""
	Returns two dicts with the peptide indices (w.r.t. dataframe df) associated with each protein in the df as a
	dictionary. One dict (min) contains only the peptide indices uniquely associated per protein, the other contains
	all peptides indices associated per protein.
	:return minProteinPeptidesDict:	dict	{ protein : uniquely associated peptide indices }
	:return maxProteinPeptidesDict:	dict	{ protein : all associated peptide indices }
	:return 						list	peptide sequences without master protein accession
	"""
	# todo make this function independent of # protein groups
	numProteinGroupsDict = df.groupby("# Protein Groups").groups  # { # Protein Groups : indices }
	# DEFAULTDICT doesn't return a KeyError when key not found, but rather None. !!! so you can safely .extend()
	minProteinPeptidesDict = None  # proteins get contribution only from peptides which correspond uniquely to them
	maxProteinPeptidesDict = None  # proteins get maximal contribution from all corresponding peptides even if corresponding to multiple proteins
	noMasterProteinAccession = []
	for numGroups, peptideIndices in numProteinGroupsDict.items():
		if numGroups == 0:
			warn("Peptides without Master Protein Accession detected. Omitting them in the analysis.")
			noMasterProteinAccession.extend(peptideIndices)
		elif numGroups == 1:  # these have only 1 master protein accession
			# { protein : indices }
			minProteinPeptidesDict = df.loc[peptideIndices].groupby("Master Protein Accessions").groups
			maxProteinPeptidesDict = defaultdict(list, minProteinPeptidesDict.copy())
		else:  # multiple proteins accessions per peptide: save those to maxProteinPeptidesDict only.
			# { multiple proteins : indices }
			multipleProteinPeptidesDict = df.loc[peptideIndices].groupby("Master Protein Accessions").groups
			# cast dict values from int64index to list # todo find a non-ugly fix
			maxProteinPeptidesDict = defaultdict(list, dict((k,list(v)) for k,v in maxProteinPeptidesDict.items()))  # ugly
			for multipleProteinsString, nonUniqueIndices in multipleProteinPeptidesDict.items():
				multipleProteins = multipleProteinsString.split('; ')
				for protein in multipleProteins: # extend the possibly (probably) already existing entry in the dict.
					maxProteinPeptidesDict[protein].extend(nonUniqueIndices)
	# 3rd return argument must be a dataframe!
	return minProteinPeptidesDict, maxProteinPeptidesDict, df.loc[noMasterProteinAccession, ['First Scan', 'Annotated Sequence']]


def getProteinDF(df, proteinPeptidesDict, intensityColumnsPerCondition):
	# todo docu
	proteinDF = pd.DataFrame([list(proteinPeptidesDict.keys())].extend([[None, ]*len(proteinPeptidesDict.keys()), ]*3),
	                         columns=['protein', 'peptides', 'condition 1', 'condition 2']).set_index('protein')
	for protein, peptideIndices in proteinPeptidesDict.items():
		# combine all channels into one channel per condition
		condition1Intensities = pd.concat([df.loc[peptideIndices, channel] for channel in
										   intensityColumnsPerCondition[0]], axis=0, ignore_index=True).tolist()
		condition2Intensities = pd.concat([df.loc[peptideIndices, channel] for channel in
										   intensityColumnsPerCondition[1]], axis=0, ignore_index=True).tolist()
		# fill new dataframe on protein level, per condition
		proteinDF.loc[protein, :] = [df.loc[peptideIndices, 'Annotated Sequence'].tolist(), condition1Intensities, condition2Intensities]
	return proteinDF


def applyDifferentialExpression(this_proteinDF, alpha):
	# todo docu
	# { protein : indices of (uniquely/all) associated peptides }
	# perform t-test on the intensities lists of both conditions of each protein, assuming data is independent.
	this_proteinDF['p-value'] = this_proteinDF.apply(lambda x: ttest(x['condition 1'], x['condition 2'], nan_policy='omit')[1], axis=1)
	# remove masked values
	this_proteinDF.loc[:, 'p-value'] = this_proteinDF.loc[:, 'p-value'].apply(lambda x: np.nan if x is np.ma.masked else x)
	# Benjamini-Hochberg correction
	# is_sorted==false &&returnsorted==false makes sure that the output is in the same order as the input.
	__, this_proteinDF['adjusted p-value'], __, __ = multipletests(pvals=np.asarray(this_proteinDF.loc[:, 'p-value']),
																   alpha=alpha, method='fdr_bh', is_sorted=False, returnsorted=False)
	return this_proteinDF


def applyFoldChange(proteinDF, pept2protCombinationMethod):
	""" Calculate the fold change for each protein (pept2protCombinationMethod) and apply it to the given protein dataframe """
	# todo proper docu
	if pept2protCombinationMethod == 'mean':
		proteinDF['fold change c1/c2'] = proteinDF.apply(lambda x: np.nanmean(x['condition 1'])/np.nanmean(x['condition 2']), axis=1)
	elif pept2protCombinationMethod == 'median':
		proteinDF['fold change c1/c2'] = proteinDF.apply(lambda x: np.nanmedian(x['condition 1']) / np.nanmedian(x['condition 2']), axis=1)
	return proteinDF


def getPCA(intensities, nComponents):
	"""
	Returns a PCA object for the transposed intensity matrix, with nComponents principal components. This means the
	reporter channels are "observations" with each protein intensity as a variable/attribute. The fast randomized method
	by Halko et al. (2009) is used for calculating the SVD. Missing values are imputed to be 1/N.
	:param intensities: np.ndarray  MxN ndarray with intensities
	:param nComponents: int         number of PC to keep
	:return pca:        PCA object  object containing the attributes of the PCA
	"""
	pca = PCA(n_components=nComponents, svd_solver='randomized')
	imputedTransposedIntensities = np.asarray(pd.DataFrame(intensities).fillna(1/intensities.shape[1])).T
	pca.fit(imputedTransposedIntensities)
	return pca


def getHC(intensities):
	"""
	Perform hierarchical clustering on the transposed intensity matrix, with nComponents principal components.
	This means the reporter channels are "observations" with each protein intensity as a variable/attribute.
	Returns the (NxN) linkage matrix describing the distances between each observation (reporter channel).
	:param intensities: np.ndarray  MxN ndarray with intensities
	:param nClusters:   int         number of clusters we want to find (= number of conditions in the experiment(s))
	:return:            np.ndarray  NxN linkage matrix
	"""
	return None #linkage(intensities.T, method='ward')


def dataVisualization(minProteinDF, fullProteinDF, alpha, FCThreshold, PCAResult, HCResult):
	# TODO (if paying customer): parameter: intensity matrix on peptide or protein level?
	# TODO: only include differentials with a fold of >threshold or <1/threshold
	visualizationsDict = {'volcano', 'pca', 'hcd'}

	# PCA plot
	PCAPlot = plt.figure(figsize=(6, 5)) # size(inches wide, height); a4paper: width = 8.267in; height 11.692in
	plt.title('Hierarchical Clustering Dendrogram', figure=PCAPlot)
	plt.xlabel('reporter channel', figure=PCAPlot)
	plt.ylabel('distance', figure=PCAPlot)


	# hierarchical clustering dendrogram
	HCDendrogram = plt.figure(figsize=(6, 5)) # size(inches wide, height); a4paper: width = 8.267in; height 11.692in
	plt.title('Hierarchical Clustering Dendrogram', figure=HCDendrogram)
	plt.xlabel('reporter channel', figure=HCDendrogram)
	plt.ylabel('distance', figure=HCDendrogram)
	dendrogram(HCResult, leaf_rotation=0., leaf_font_size=12., figure=HCDendrogram)
	plt.show(figure=HCDendrogram) # TEST
	visualizationsDict['hcd'] = HCDendrogram
	return visualizationsDict