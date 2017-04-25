#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Python implementation of mass spectrometer protein data analysis using the CONSTANd_RAS algorithm.
"""

import sys, logging, datetime
from constandpp.dataIO import *


def main(jobConfigFilePath, doProcessing, doAnalysis, doReport, writeToDisk, testing):
	"""
	For now this is just stuff for debugging and testing. Later:
	Contains and explicits the workflow of the program. Using the booleans doProcessing, doAnalysis and writeToDisk one
	can control	which parts of the workflow to perform.
	"""
	# todo proper docu
	from constandpp.getInput import getProcessingInput, getJobInput
	from constandpp.processingFlow import processDf
	from constandpp.analysisFlow import analyzeProcessingResult
	from constandpp.reportFlow import generateReport
	from time import time
	from constandpp_web.web import DB_setJobReportRelPaths
	
	logFilePath = os.path.abspath(os.path.join(jobConfigFilePath, os.path.join(os.pardir, 'log.txt')))
	logging.basicConfig(filename=logFilePath, level=logging.INFO)
	start = time()
	jobParams = getJobInput(jobConfigFilePath)  # config filenames + params for the combination of experiments
	processingParams = {}  # specific params for each experiment
	dfs = {}
	processingResults = {}
	experimentNames = list(jobParams['schema'].keys())
	
	for eName in experimentNames:
		""" Data processing """
		# get all input parameters
		processingParams[eName] = getProcessingInput(jobParams['schema'][eName]['config'])
		# get the dataframes
		dfs[eName] = importExperimentData(processingParams[eName]['data'], delim=processingParams[eName]['delim_in'],
										  header=processingParams[eName]['header_in'],
										  wrapper=processingParams[eName]['wrapper'])
		processing_path_out = processingParams[eName]['path_out']
		processingResultsDumpFilename = os.path.join(processing_path_out, 'processingResultsDump_' + str(eName))
		if doProcessing:
			print('Starting processing of ' + eName + '...')
			# prepare the output directories
			if not os.path.exists(os.path.abspath(processing_path_out)):  # do not overwrite dir
				assert os.path.exists(
					os.path.abspath(os.path.join(processing_path_out, os.path.pardir)))  # parent dir must exist
				os.makedirs(processing_path_out)
			else:
				if jobConfigFilePath != 'job/jobConfig.ini':  # TEST
					raise Exception(
						"Output path " + os.path.abspath(processing_path_out) + " already exists! Aborting.")
			
			# process every input dataframe
			logging.info(
				"Starting processing of experiment '" + eName + "' of job '" + jobParams['jobname'] + "' at " +
				str(datetime.datetime.now()).split('.')[0])
			processingResults[eName] = processDf(dfs[eName], processingParams[eName], writeToDisk)
			logging.info(
				"Finished processing of experiment '" + eName + "' of job '" + jobParams['jobname'] + "' at " +
				str(datetime.datetime.now()).split('.')[0])
			pickle.dump(processingResults[eName], open(processingResultsDumpFilename, 'wb'))  # TEST
		elif doAnalysis:
			try:
				processingResults[eName] = pickle.load(open(processingResultsDumpFilename, 'rb'))
			except FileNotFoundError:
				raise FileNotFoundError(
					"There is no previously processed data in this path: " + processingResultsDumpFilename)
		else:
			logging.warning(
				"No processing step performed nor processing file loaded for experiment " + str(eName) + "!")
	
	""" Data analysis """
	analysis_path_out = jobParams['path_out']
	analysisResultsDumpFilename = os.path.join(analysis_path_out, 'analysisResultsDump')
	if doAnalysis:
		print('Starting analysis...')
		# prepare the output directories
		if not os.path.exists(analysis_path_out):  # do not overwrite dir
			assert os.path.exists(
				os.path.abspath(os.path.join(analysis_path_out, os.path.pardir)))  # parent dir must exist
			os.makedirs(analysis_path_out)
		
		# perform analysis
		logging.info("Starting analysis of job: " + jobParams['jobname'] + " at " +
					 str(datetime.datetime.now()).split('.')[0])
		analysisResults = analyzeProcessingResult(processingResults, jobParams, writeToDisk)
		logging.info("Finished analysis of job: " + jobParams['jobname'] + " at " +
					 str(datetime.datetime.now()).split('.')[0])
		pickle.dump(analysisResults, open(analysisResultsDumpFilename, 'wb'))  # TEST
	elif doReport:
		try:
			analysisResults = pickle.load(open(analysisResultsDumpFilename, 'rb'))
		except FileNotFoundError:
			raise FileNotFoundError(
				"There is no previously analyzed data in this path: " + analysisResultsDumpFilename)
	else:
		logging.warning("No analysis step performed nor analysis file loaded!")
	
	""" Visualize and generate report """
	results_path_out = jobParams['path_results']
	
	if doReport:
		print('Starting visualization and report generation...')
		# prepare the output directories
		if not os.path.exists(results_path_out):  # do not overwrite dir
			assert os.path.exists(
				os.path.abspath(os.path.join(results_path_out, os.path.pardir)))  # parent dir must exist
			os.makedirs(results_path_out)
		
		# visualize and make a report
		logging.info("Starting visualization end report generation of job: " + jobParams['jobname'] + "at " +
					 str(datetime.datetime.now()).split('.')[0])
		generateReport(analysisResults, jobParams, logFilePath, writeToDisk, processingParams, start)
		DB_setJobReportRelPaths(jobID=jobDirName, resultpath=jobParams['path_results'],
								jobName=jobParams['jobname'])
		logging.info("Finished visualization end report generation of job: " + jobParams['jobname'] + "at " +
					 str(datetime.datetime.now()).split('.')[0])
	else:
		logging.warning("No report generated!")
	stop = time()
	print(stop - start)


if __name__ == '__main__':  # this should not execute if main.py is not the main module called by the python interpreter,
	from constandpp_web.web import DB_setJobCompleted, DB_setJobFailed
	from constandpp_web import app
	from traceback import print_exc
	
	args = sys.argv
	print(str(args))  # TEST
	if len(args) != 1:
		assert len(args) == 7  # todo use argparser
		jobConfigFilePath = args[1]
		doProcessing = (args[2] == 'True')
		doAnalysis = (args[3] == 'True')
		doReport = (args[4] == 'True')
		writeToDisk = (args[5] == 'True')
		testing = (args[6] == 'True')
	# so if you start main.py from within web.py or something, this won't be executed
	else:
		doProcessing = False
		doAnalysis = False
		doReport = True
		writeToDisk = True
		testing = False
		
		# jobConfigFilePath = 'job/jobConfig.ini' # TEST
		jobConfigFilePath = '../jobs/2017-01-23 02:40:26.553814_two/jobConfig_two.ini'
	# jobConfigFilePath = webFlow(exptype='COON')
	# jobConfigFilePath = webFlow(exptype='COON', previousjobdirName='2016-12-26 10:56:10.646919_COON')
	# jobConfigFilePath = webFlow(exptype='COON_SN')
	# jobConfigFilePath = webFlow(exptype='COON_SN', previousjobdirName='2016-12-20 14:21:47.786288_COON_SN')
	# jobConfigFilePath = webFlow(exptype='COON_norm') # todo constand uitzetten
	# jobConfigFilePath = webFlow(exptype='COON_norm', previousjobdirName='2016-12-12 22:43:38.030716_COON_norm')
	# jobConfigFilePath = webFlow(exptype='COON_SN_norm')  # todo constand uitzetten
	# jobConfigFilePath = webFlow(exptype='COON_SN_norm', previousjobdirName='2016-12-12 22:48:30.701250_COON_SN_norm')
	# jobConfigFilePath = webFlow(exptype='COON_nonormnoconstand')  # todo constand uitzetten
	# jobConfigFilePath = webFlow(exptype='COON_nonormnoconstand', previousjobdirName='2016-12-20 14:31:47.045927_COON_nonormnoconstand')
	# jobConfigFilePath = webFlow(exptype='COON_noISO')
	# jobConfigFilePath = webFlow(exptype='COON_noISO', previousjobdirName='2016-12-16 16:38:30.536344_COON_noISO')
	# jobConfigFilePath = webFlow(exptype='COON_SN_nonormnoconstand')  # todo constand uitzetten
	# jobConfigFilePath = webFlow(exptype='COON_SN_nonormnoconstand', previousjobdirName='2016-12-20 14:39:09.476567_COON_SN_nonormnoconstand')
		jobConfigFilePath = '/home/pdiracdelta/Documents/UHasselt/CONSTANd++/jobs/2017-04-14 17:46:37.527494_alleswerkt?/jobConfig_alleswerkt?.ini'
	
	with app.app_context():
		jobDirName = os.path.basename(os.path.abspath(os.path.join(jobConfigFilePath, os.pardir)))
		try:
			main(jobConfigFilePath=jobConfigFilePath, doProcessing=doProcessing, doAnalysis=doAnalysis,
				 doReport=doReport,
				 testing=testing, writeToDisk=writeToDisk)
			DB_setJobCompleted(jobDirName)
		except:
			DB_setJobFailed(jobDirName)
			print_exc()
