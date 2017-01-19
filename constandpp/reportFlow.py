#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Workflow of the processing part of CONSTANd++.
"""

from report import *
from dataIO import exportData


def generateReport(analysisResults, params, logFilePath, writeToDisk):
	# todo docu
	minProteinDF = analysisResults[0]
	fullProteinDF = analysisResults[1]
	PCAResult = analysisResults[2]
	HCResult = analysisResults[3]
	allExperimentsIntensitiesPerCommonPeptide = np.asarray(analysisResults[4])
	metadata = analysisResults[5]

	### TEST
	testInterexperimentalOnPeptideLevel = False
	proteinLevelMAPlots = False
	if testInterexperimentalOnPeptideLevel:
		from main import MAPlot
		org3data = allExperimentsIntensitiesPerCommonPeptide[:, 17]
		#MAPlot(org3data, allExperimentsIntensitiesPerCommonPeptide[:, 11],
		#       'org2 exp [1] vs org2 exp [1]')
		MAPlot(org3data, allExperimentsIntensitiesPerCommonPeptide[:, 18],
		       'org2 exp [2] vs org3 exp [2]')
		MAPlot(org3data, allExperimentsIntensitiesPerCommonPeptide[:, 26],
		       'org2 exp [2] vs org3 exp [3]')
	if proteinLevelMAPlots:
		from main import MAPlot
		MAPlot(minProteinDF.loc[:, '3_muscle'], minProteinDF.loc[:, '4_muscle'],
		       'org2 exp [2] vs org3 exp [2]')
		MAPlot(minProteinDF.loc[:, '3_muscle'], minProteinDF.loc[:, '4_cerebrum'],
		       'org2 exp [2] vs org3 exp [3]')

	nConditions = len(list(params['schema'].values())[0]['channelAliasesPerCondition'])
	# ONLY PRODUCE VOLCANO AND DEA IF CONDITIONS == 2
	if nConditions == 2:
		# generate sorted (on p-value) list of differentials
		if params['minExpression_bool']:
			minSortedDifferentialProteinsDF = getSortedDifferentialProteinsDF(minProteinDF)
			minSet = set(minSortedDifferentialProteinsDF['protein'])
			# data visualization
			minVolcanoPlot = getVolcanoPlot(minProteinDF, params['alpha'], params['FCThreshold'],
			                                params['labelVolcanoPlotAreas'])
		if params['fullExpression_bool']:
			fullSortedDifferentialProteinsDF = getSortedDifferentialProteinsDF(fullProteinDF)
			fullSet = set(fullSortedDifferentialProteinsDF['protein'])
			# data visualization
			fullVolcanoPlot = getVolcanoPlot(fullProteinDF, params['alpha'], params['FCThreshold'],
			                                 params['labelVolcanoPlotAreas'])
		if params['minExpression_bool'] and params['fullExpression_bool']:
			# list( [in min but not in full], [in full but not in min] )
			metadata['diffMinFullProteins'] = [list(minSet.difference(fullSet)), list(fullSet.difference(minSet))]
			# todo combine into one

		if writeToDisk:
			if params['minExpression_bool']:
				exportData(minSortedDifferentialProteinsDF, dataType='df', path_out=params['path_results'],
				           filename=params['jobname'] + '_minSortedDifferentials', delim_out='\t')
				exportData(minVolcanoPlot, dataType='fig', path_out=params['path_results'],
				           filename=params['jobname'] + '_minVolcanoPlot')
			if params['fullExpression_bool']:
				exportData(fullSortedDifferentialProteinsDF, dataType='df', path_out=params['path_results'],
						   filename=params['jobname'] + '_fullSortedDifferentials', delim_out='\t')
				exportData(fullVolcanoPlot, dataType='fig', path_out=params['path_results'],
				           filename=params['jobname'] + '_fullVolcanoPlot')
	else:
		minSortedDifferentialProteinsDF = pd.DataFrame()
		fullSortedDifferentialProteinsDF = pd.DataFrame()
		minVolcanoPlot = None
		fullVolcanoPlot = None

	PCAPlot = getPCAPlot(PCAResult, params['schema'])
	if writeToDisk:
		exportData(PCAPlot, dataType='fig', path_out=params['path_results'],
		           filename=params['jobname'] + '_PCAPlot')
	HCDendrogram = getHCDendrogram(HCResult, params['schema'])
	if writeToDisk:
		exportData(HCDendrogram, dataType='fig', path_out=params['path_results'],
		           filename=params['jobname'] + '_HCDendrogram')

	# generate HTML and PDF reports # todo
	htmlReport = makeHTML(minSortedDifferentialProteinsDF, fullSortedDifferentialProteinsDF, params['numDifferentials'], minVolcanoPlot,
	                      fullVolcanoPlot, PCAPlot, HCDendrogram, metadata, logFilePath)
	pdfReport = HTMLtoPDF(htmlReport)

	if writeToDisk:
		exportData(htmlReport, dataType='html', path_out=params['path_results'],
		           filename=params['jobname'] + '_report')
