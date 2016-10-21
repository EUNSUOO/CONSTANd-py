#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Collection of functions that help removing redundancy in the data due to detections which have:
* different retention time (RT) values
* different charges
* different (post-translational) modifications (PTMs)
and replaces the duplicates with one representative detection and a combination/summary/selection of their intensities.
"""

import numpy as np
from dataprep import intensityColumns, setIntensities, getIntensities

columnsToSave = None


def setCollapseColumnsToSave(columnsToSave):
	"""
	Sets the value of the global variable columnsToSave for use in the module functions.
	:param columnsToSave: list   names of the columns that ought to be saved when removing data in a collapse.
	"""
	globals()['columnsToSave'] = columnsToSave


def getDuplicates(toCollapse, df, indices, checkTrueDuplicates, undoublePSMAlgo_bool):
	"""
	Takes a list of indices of candidate-duplicates (all df entries with identical annotated sequence) and returns
	a dict of first occurrences and their true duplicates due to charge difference, as well as the corresponding
	data extracted from the original dataFrame df. First occurrences without duplicates do not appear in the dict.
	:param df:                  pd.dataFrame    data which is to be checked for duplicates
	:param indices:             list            indices of the locations of candidate-duplicates in the original dataFrame df.
	:param checkTrueDuplicates: function        function which returns True if two entries given as arguments are true duplicates.
	:return duplicatesDict:     dict            {firstOccurrenceIndex:[duplicateIndices]}
	:return duplicatesDf:       pd.dataFrame    data of only the entries involved in true duplication due to charge
	"""
	import pandas as pd

	duplicateLists = [] # [list of [list of duplicate indices] for each duplicate]

	def groupByIdenticalProperties(byPropDict, remainingProperties):
		# todo: if the code inside this function doesnt work, use the one outside this function instead
		if remainingProperties:
			for prop, byPropIndices in byPropDict:
				if len(byPropIndices)>1: # only if there are duplicates
					## SELECT IDENTICAL <NEXTPROPERTY> ##
					groupByIdenticalProperties(df[byPropIndices].groupby(remainingProperties[0]), remainingProperties[1:], undoublePSMAlgo_bool)
		else:
			duplicateLists.extend(byPropDict.values)
		return duplicateLists

	youreFeelingLucky = True # todo: disable this if the code above doesnt work (TRIGGERS CODE IN FUNCTION ABOVE)
	if youreFeelingLucky:
		properties=[]
		if not undoublePSMAlgo_bool:  # only if you didn't undoublePSMAlgo
			## SELECT IDENTICAL PSMALGO (i.e. different First Scan) ##
			byPSMAlgoDict = df.groupby('Identifying Node').groups
			properties.append('Annotated Sequence')
		else:
			## SELECT IDENTICAL SEQUENCE ##
			bySequenceDict = df.groupby('Annotated Sequence').groups
		if toCollapse == 'RT':
			groupByIdenticalProperties(bySequenceDict, properties+['Charge', 'Modifications'])
			return duplicateLists
		elif toCollapse == 'Charge':
			groupByIdenticalProperties(bySequenceDict, properties+['Modifications'])
		elif toCollapse == 'PTM':
			groupByIdenticalProperties(bySequenceDict, properties+['Charge'])
		return duplicateLists

	elif not youreFeelingLucky:
		## SELECT IDENTICAL SEQUENCE ##
		bySequenceDict = df.groupby('Annotated Sequence').groups
		if toCollapse == 'RT':
			for sequence, bySequenceIndices in bySequenceDict:
				if len(bySequenceIndices)>1: # only if there are duplicates
					## SELECT IDENTICAL CHARGE ##
					byChargeBySequenceDict = df[bySequenceIndices].groupby('Charge').groups
					for charge, byChargeIndices in byChargeBySequenceDict:
						if len(byChargeIndices) > 1:  # only if there are duplicates
							## SELECT IDENTICAL PTM ##
							byPTMByChargeBySequenceDict = df[byChargeIndices].groupby('Modifications').groups
							if not undoublePSMAlgo_bool: # only if you didn't undoublePSMAlgo
								for PTM, byPTMIndices in byPTMByChargeBySequenceDict:
									if len(byPTMIndices) > 1:  # only if there are duplicates
										## SELECT IDENTICAL PSMALGO (i.e. different First Scan) ##
										byPSMAlgoByPTMByChargeBySequenceDict = df[byPTMIndices].groupby('Identifying Node').groups
										duplicateLists.extend(byPSMAlgoByPTMByChargeBySequenceDict.values)
							else:
								duplicateLists.extend(byPTMByChargeBySequenceDict.values)

		elif toCollapse == 'Charge':
			for sequence, bySequenceIndices in bySequenceDict:
				if len(bySequenceIndices)>1: # only if there are duplicates
					## SELECT IDENTICAL PTM ##
					byPTMBySequenceDict = df[bySequenceIndices].groupby('Modifications').groups
					if not undoublePSMAlgo_bool:  # only if you didn't undoublePSMAlgo
						for PTM, byPTMIndices in byPTMBySequenceDict:
							if len(byPTMIndices) > 1:  # only if there are duplicates
								## SELECT IDENTICAL PSMALGO (i.e. different First Scan) ##
								byPSMAlgoByPTMBySequenceDict = df[byPTMIndices].groupby('Identifying Node').groups
								duplicateLists.extend(byPSMAlgoByPTMBySequenceDict.values)
					else: # you did undoublePSMAlgo? Great, you're done.
						duplicateLists.extend(byPTMBySequenceDict.values)
					## SANITY CHECK ##
					for PTM, byPTMIndices in byPTMBySequenceDict: # TEST
						if len(byPTMIndices) > 1:  # only if there are duplicates
							## SELECT IDENTICAL CHARGE ##
							byChargeByPTMBySequenceDict = df[byPTMIndices].groupby('Charge').groups
							for charge, byChargeIndices in byChargeByPTMBySequenceDict:
								assert len(byChargeIndices) < 2 # if same Sequence and same PTM, Charge cannot be the same because it would have been RT-collapsed.

		elif toCollapse == 'PTM':
			for sequence, bySequenceIndices in bySequenceDict:
				if len(bySequenceIndices)>1: # only if there are duplicates
					## SELECT IDENTICAL CHARGE ##
					byChargeBySequenceDict = df[bySequenceIndices].groupby('Charge').groups
					if not undoublePSMAlgo_bool:  # only if you didn't undoublePSMAlgo
						for charge, byChargeIndices in byChargeBySequenceDict:
							if len(byChargeIndices) > 1:  # only if there are duplicates
								## SELECT IDENTICAL PSMALGO ##
								byPSMAlgoByChargeBySequenceDict = df[byChargeIndices].groupby('Identifying Node').groups
								duplicateLists.extend(byPSMAlgoByChargeBySequenceDict.values)
					else: # you did undoublePSMAlgo? Great, you're done.
						duplicateLists.extend(byChargeBySequenceDict.values)
					## SANITY CHECK ##
					for charge, byChargeIndices in byChargeBySequenceDict: # TEST
						if len(byChargeIndices) > 1:  # only if there are duplicates
							## SELECT IDENTICAL PTM ##
							byPTMByChargeBySequenceDict = df[byChargeIndices].groupby('Modifications').groups
							for PTM, byPTMIndices in byPTMByChargeBySequenceDict:
								assert len(byPTMIndices) < 2 # if same Sequence and same Charge, PTM cannot be the same because it would have been RT-collapsed.
		return duplicateLists


def combineDetections(duplicatesDf, centerMeasure):
	if centerMeasure == 'mean':
		pass
	if centerMeasure == 'geometricMedian':
		pass
	if centerMeasure == 'weighted':
		pass
	return newIntensities # TODO


def getRepresentative(duplicatesDf, duplicatesDict, masterPSMAlgo):
	# get the detection with the best PSM match
	# values of BEST PSM detection in all duplicates (master/slave-wise best)
	# dont forget to increase Degeneracy # todo

	return detection # TODO


def getNewIntensities(df, duplicateLists, method, maxRelativeReporterVariance, masterPSMAlgo):
	"""
	Combines the true duplicates' intensities into one new entry per first occurrence, conform the duplicatesDict structure.
	:param duplicatesDict:          dict            {firstOccurrenceIndex:[duplicateIndices]}
	:param duplicatesDf:            pd.dataFrame    data of only the first occurrences and duplicates
	:return newIntensitiesDict:     dict            {firstOccurrenceIndex:np.array(newIntensities)}
	"""
	import warnings
	weightedMS2Intensities = {}  # dict with the new MS2 intensities for each firstOccurrence
	if False:  # TODO flag isolated peaks
		pass
	if method == 'bestMatch':
		newIntensities = None
		representative = getRepresentative(duplicatesDf, duplicatesDict, masterPSMAlgo)
		pass # TODO
	elif method == 'mostIntense':
		newIntensities = None
		representative = getRepresentative(duplicatesDf, duplicatesDict, masterPSMAlgo)
		pass # TODO
	else:
		newIntensities = combineDetections(duplicatesDf, centerMeasure=method)
		representative = getRepresentative(duplicatesDf, duplicatesDict, masterPSMAlgo)
	# TODO the next section is obsolete if you use combineDetections
	for firstOccurrence, duplicates in duplicatesDict:  # TODO flag PTM differences.
		totalMS1Intensity = sum(duplicatesDf.loc[[firstOccurrence] + duplicates]['Intensity'])
		allWeights = duplicatesDf.loc[[firstOccurrence] + duplicates][
			             'Intensity'] / totalMS1Intensity  # TODO this is very probably NOT correct: you are weighting absolute MS2 intensities by MS1 intensity
		allMS2Intensities = getIntensities(duplicatesDf.loc[[firstOccurrence] + duplicates])  # np.array
		weightedMS2Intensities[firstOccurrence] = np.sum((allMS2Intensities.T * allWeights).T,
		                                                 0)  # TODO check if the dimension are correct
		if np.any(np.var(allMS2Intensities,
		                 0) > maxRelativeReporterVariance):  # TODO this can only be consistent if executed on RELATIVE intensities.
			warnings.warn(
				"maxRelativeReporterVariance too high for peptide with index " + firstOccurrence + ".")  # TODO this shouldnt just warn, you should also decide what to do.
	return newIntensitiesDict


def collapse(toCollapse, df, method, maxRelativeReporterVariance, masterPSMAlgo, undoublePSMAlgo_bool): #
	"""
	Generic collapse function. Looks for duplicate 'Annotated Sequence' values in the dataFrame and verifies
	true duplication using checkTrueDuplicates function. Modifies df according to true duplicates and newly acquired
	intensities (via getNewIntensities function): remove all duplicates and enter one replacement detection.
	Adds a 'Degeneracy' column to the dataFrame if it didn't exist already: this contains the number of peptides that
	have been collapsed onto that (synthetic) detection.
	Returns removedData according to the columnsToSave list.
	:param toCollapse:                  str             variable of which true duplicates are to be collapsed.
	:param df:                          pd.dataFrame    with sequence duplicates due to difference in certain variables/columns.
	:param columnsToSave:                  list            list of variables to be saved for detections that ought to be removed
	:param method:                      str             defines how the new detection is to be selected/constructed
	:param maxRelativeReporterVariance: float           UNUSED value that restricts reporter variance
	:return df:                         pd.dataFrame    without sequence duplicates according to to checkTrueDuplicates.
	:return removedData:                dict            {firstOccurrenceIndex : [annotated_sequence, [other, values, to, be, saved] for each duplicate]}
	"""

	if 'Degeneracy' not in df.columns:
		# contains the number of peptides that have been collapsed onto each (synthetic) detection.
		df['Degeneracy'] = [1,]*len(df.index)

	if toCollapse == 'RT':
		def checkTrueDuplicates(x, y):
			"""
			Checks whether dataFrame entries x and y are truly duplicates only due to RT difference.
			:param x:   pd.Sequence candidate firstOccurrence data
			:param y:   pd.Sequence candidate duplicate data
			"""
			if x['Charge'] != y['Charge']:  # different charge = different ("modified, non-redundant") peptide
				return False
			if x['Modifications'] != y['Modifications']:  # different PTM = different sequence (before collapsePTM() anyway).
				return False
			if x['First Scan'] == y['First Scan']:  # identical peptides have identical RT
				# THIS SHOULD NOT BE REACHABLE ***UNLESS*** YOU DIDNT COLLAPSEPSMALGO()
				return False
			return True

	elif toCollapse == 'Charge':
		def checkTrueDuplicates(x, y):
			"""
			Checks whether dataFrame entries x and y are truly duplicates only due to charge difference.
			:param x:   pd.Sequence candidate firstOccurrence data
			:param y:   pd.Sequence candidate duplicate data
			"""
			if x['Charge'] == y['Charge']:  # well obviously they should duplicate due to charge difference...
				return False
			if x['Modifications'] != y[
				'Modifications']:  # different PTM = different sequence (before collapsePTM() anyway).
				return False
			if x['First Scan'] == y['First Scan']:  # identical peptides have identical RT
				# THIS SHOULD NOT BE REACHABLE ***UNLESS*** YOU DIDNT COLLAPSEPSMALGO()
				return False
			return True

	elif toCollapse == 'PTM':
		def checkTrueDuplicates(x, y):
			"""
			Checks whether dataFrame entries x and y are truly duplicates only due to PTM difference.
			:param x:   pd.Sequence candidate firstOccurrence data
			:param y:   pd.Sequence candidate duplicate data
			"""
			if x['Modifications'] == y['Modifications']:
				# THIS SHOULD NOT BE REACHABLE ***UNLESS*** YOU DIDNT PERFORM ALL PREVIOUS COLLAPSES
				return False
			if x['Charge'] != y['Charge']:  # well obviously they should duplicate due to charge difference...
				# THIS SHOULD NOT BE REACHABLE ***UNLESS*** YOU DIDNT COLLAPSECHARGE()
				return False
			if x['First Scan'] == y['First Scan']:  # identical peptides have identical RT
				# THIS SHOULD NOT BE REACHABLE ***UNLESS*** YOU DIDNT COLLAPSEPSMALGO()
				return False
			return True

	allSequences = df.groupby('Annotated Sequence').groups  # dict of SEQUENCE:[INDICES]
	allDuplicatesHierarchy = {}  # {firstOccurrence:[duplicates]}
	for sequence, indices in allSequences.items():
		if len(indices) > 1:  # only treat duplicated sequences
			# dict with duplicates per first occurrence, dataFrame with df indices but with only the duplicates
			duplicateLists = getDuplicates(toCollapse, df, indices, checkTrueDuplicates, undoublePSMAlgo_bool)
			# get the new intensities per first occurrence index (df index)
			intensitiesDict = getNewIntensities(df, duplicateLists, method, maxRelativeReporterVariance, masterPSMAlgo)
			allDuplicatesHierarchy.update(duplicatesDict)
	setIntensities(df, intensitiesDict)
	toDelete = list(allDuplicatesHierarchy.values())
	# save as {firstOccurrenceIndex : [annotated_sequence, [values, to, be, saved] for each duplicate]}
	removedData = dict((firstOccurrence, [df.loc[firstOccurrence][columnsToSave[0]],
	                                      df.loc[allDuplicatesHierarchy[firstOccurrence]][columnsToSave[1:]]])
	                   for firstOccurrence in allDuplicatesHierarchy.keys())
	df.drop(toDelete, inplace=True)

	return df, removedData
