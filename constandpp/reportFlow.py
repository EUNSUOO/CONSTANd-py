#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
Workflow of the processing part of CONSTANd++.
"""

from constandpp.report import *
from constandpp.dataIO import exportData, genZip


def generateReport(analysisResults, params, logFilePath, writeToDisk, processingParams, startTime):
	"""
	Calls all the necessary functions to make visualizations and generate an HTML and PDF report.
	Takes an analysisResults object and uses the PCA and HC to generate a 2D PC plot as well as a HC dendrogram. If
	nConditions==2 then volcano plots for minExpression (injective) and fullExpression (non-injective, if available) are
	also produced and for each expression type a list of top differentials (according to adjusted p-value) is constructed.
	They are poured into an HTML report together with the parameters and metadata, and then converted into a PDF report.
	Because of technical reasons to do with image representation, the PDF is generated from a slightly different HTML
	file than the "public" HTML file.
	Graphs and report files are written to disk if so specified by writeToDisk.
	:param analysisResults:	list	[minProteinDF, fullProteinDF, PCAResult, HCResult, allExperimentsIntensitiesPerCommonPeptide]
	:param params:			dict	job (global) parameters
	:param logFilePath:		str		path to the log file with information about each processingFlow and analysisFlow call
	:param writeToDisk:		bool	write visualizations and reports to disk (if not: just pass the return statement)
	:param processingParams:dict	experiment-specific processing parameters (see getInput.py.)
	:param startTime:		float	UNIX epoch timestamp at which the reportFlow was started
	"""
	minProteinDF = analysisResults[0]
	fullProteinDF = analysisResults[1]
	PCAResult = analysisResults[2]
	HCResult = analysisResults[3]
	metadata = analysisResults[5]
	
	otherConditions = getOtherConditions(params['schema'], params['referenceCondition'])

	def getExpressionResults(this_proteinDF, this_schema):
		"""
		Sorts the protein dataframe, calculates the set of proteins in the results, generates a volcano plot and selects the
		top differentials by calling functions from report.py
		:param this_proteinDF:						pd.DataFrame    unsorted DE analysis results on the protein level
		:return this_sortedProteinExpressionsDF:	dict			DEA output table sorted according to adjusted p-value,
																	including proteins without DE results, per condition
		:return this_topDifferentialsDFs:			dict			top X sorted (on adjusted p-value) proteins, per condition
		:return this_volcanoPlot:					dict			plt.figure volcano plot, per condition
		:return this_set:							set				all proteins represented in the results
		"""
		# { condition: sortedProteinExpressionsDF }
		this_sortedProteinExpressionsDFs = getSortedProteinExpressionsDFs(this_proteinDF, this_schema, params['referenceCondition'])
		this_set = set()
		this_topDifferentialsDFs = dict()  # { condition: topDifferentialsDF }
		this_volcanoPlots = dict()  # { condition: volcanoPlot }
		# get the Expression results for each condition separately
		for otherCondition in otherConditions:
			this_set.update(set(this_sortedProteinExpressionsDFs[otherCondition]['protein']))
			# get top X differentials
			this_topDifferentialsDFs[otherCondition] = getTopDifferentials(this_sortedProteinExpressionsDFs[otherCondition], params['numDifferentials'])
			# data visualization
			this_volcanoPlots[otherCondition] = getVolcanoPlot(this_proteinDF, otherCondition, params['alpha'], params['FCThreshold'],
															 params['labelVolcanoPlotAreas'],
															 topIndices=this_topDifferentialsDFs[otherCondition].index)
			# add protein IDs that were observed at least once but got removed, for completeness in the output csv.
			this_sortedProteinExpressionsDFs[otherCondition] = addMissingObservedProteins(this_sortedProteinExpressionsDFs[otherCondition],
																						  metadata['allObservedProteins'].loc[:, 'protein'][0])
		return this_sortedProteinExpressionsDFs, this_topDifferentialsDFs, this_volcanoPlots, this_set
	
	allDEResultsFullPaths = []  # paths to later pass on for mail attachments
	# do MINIMAL expression
	if params['minExpression_bool']:
		minSortedProteinExpressionsDFs, minTopDifferentialsDFs, minVolcanoPlots, minSet = getExpressionResults(minProteinDF, params['schema'])
		# save results
		minDEResultsFullPaths = exportData(minSortedProteinExpressionsDFs, dataType='df', path_out=params['path_results'],
										  filename=params['jobName'] + '_minSortedDifferentials',
										  delim_out=params['delim_out'])
		minVolcanoFullPaths = dict((otherCondition, exportData(minVolcanoPlots[otherCondition], dataType='fig',
														   path_out=params['path_results'],
														   filename=params['jobName'] + '_minVolcanoPlot'))
							   for otherCondition in otherConditions)
		allDEResultsFullPaths.extend(list(minDEResultsFullPaths.values()))  # no need to know which path is which
		
	else:  # todo in this case (and also for fullExpression_bool) just let the jinja template handle the None variable.
		# but don't make a fake on here and then pass it onto makeHTML() like is done now.
		minSortedProteinExpressionsDF = pd.DataFrame(columns=['protein', 'significant', 'description', 'fold change log2(c1/c2)', 'adjusted p-value'])
		minTopDifferentialsDFs = pd.DataFrame(columns=minSortedProteinExpressionsDF.columns)
		minVolcanoFullPaths = None
	
	# do FULL expression
	if params['fullExpression_bool']:
		fullSortedProteinExpressionsDFs, fullTopDifferentialsDFs, fullVolcanoPlots, fullSet = getExpressionResults(fullProteinDF, params['schema'])
		# save results
		fullDEResultsFullPaths = exportData(fullSortedProteinExpressionsDFs, dataType='df',
										   path_out=params['path_results'],
										   filename=params['jobName'] + '_fullSortedDifferentials',
										   delim_out=params['delim_out'])
		fullVolcanoFullPaths = dict((otherCondition, exportData(fullVolcanoPlots[otherCondition], dataType='fig',
															path_out=params['path_results'],
															filename=params['jobName'] + '_fullVolcanoPlot'))
								for otherCondition in otherConditions)
		allDEResultsFullPaths.extend(list(fullDEResultsFullPaths.values()))  # no need to know which path is which
	else:
		fullSortedProteinExpressionsDF = pd.DataFrame(columns=['protein', 'significant', 'description', 'fold change log2(c1/c2)', 'adjusted p-value'])
		fullTopDifferentialsDFs = pd.DataFrame(columns=fullSortedProteinExpressionsDF.columns)
		fullVolcanoFullPaths = None

	# metadata
	if params['minExpression_bool'] and params['fullExpression_bool']:
		# list( [in min but not in full], [in full but not in min] )
		metadata['diffMinFullProteins'] = [list(minSet.difference(fullSet)), list(fullSet.difference(minSet))]
		# todo combine into one

	# else:
	# 	minTopDifferentialsDF = pd.DataFrame()
	# 	fullTopDifferentialsDF = pd.DataFrame()
	# 	minVolcanoFullPath = None
	# 	fullVolcanoFullPath = None

	PCAPlot = getPCAPlot(PCAResult, params['schema'])
	if writeToDisk:
		PCAPlotFullPath = exportData(PCAPlot, dataType='fig', path_out=params['path_results'],
				   filename=params['jobName'] + '_PCAPlot')
	HCDendrogram = getHCDendrogram(HCResult, params['schema'])
	if writeToDisk:
		HCDendrogramFullPath = exportData(HCDendrogram, dataType='fig', path_out=params['path_results'],
				   filename=params['jobName'] + '_HCDendrogram')

	if writeToDisk:
		htmlReport, pdfhtmlreport = makeHTML(jobParams=params, allProcessingParams=processingParams,
											 otherConditions=otherConditions,
											 minTopDifferentialsDFs=minTopDifferentialsDFs,
											 fullTopDifferentialsDFs=fullTopDifferentialsDFs,
											 minVolcanoFullPaths=minVolcanoFullPaths,
											 fullVolcanoFullPaths=fullVolcanoFullPaths,
											 PCAPlotFullPath=PCAPlotFullPath, HCDendrogramFullPath=HCDendrogramFullPath,
											 metadata=metadata, logFilePath=logFilePath, startTime=startTime)
		htmlFullPath = exportData(htmlReport, dataType='html', path_out=params['path_results'],
				   filename=params['jobName'] + '_report')
		pdfhtmlFullPath = exportData(pdfhtmlreport, dataType='html', path_out=params['path_results'],
				   filename=params['jobName'] + '_Report')

		pdfFullPath = HTMLtoPDF(pdfhtmlFullPath)
		# todo possibly remove need for special pdfhtml if weasyprint fetches the HTML from the web server via URL instead
		
		# zip the result files together (except the report file)
		from os.path import join
		resultsZipFullPath = join(params['path_results'], 'results.zip')
		genZip(resultsZipFullPath, allDEResultsFullPaths)
		
		from constandpp_web.web import send_mail
		### SEND JOB COMPLETED MAIL ###
		mailSuccess = send_mail(recipient=params['mailRecipient'], mailBodyFile='reportMail',
				  jobName=params['jobName'], jobID=params['jobID'], attachments=[pdfFullPath]+resultsZipFullPath)
		if mailSuccess is not None:  # something went wrong
			import logging
			logging.error(mailSuccess)
			print(mailSuccess)
