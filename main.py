#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Python implementation of mass spectrometer protein data analysis using the CONSTANd_RAS algorithm.
"""

__author__ = "Joris Van Houtven"
__copyright__ = "Copyright ?YEAR, VITO"
__credits__ = ["Joris Van Houtven", "Dirk Valkenborg"]
# __license__ = "GPL"
# __version__ = "0.0.1"
__maintainer__ = "Joris Van Houtven"
__email__ = "vanhoutvenjoris@gmail.com"
__status__ = "Development"

import sys, os, logging, datetime
from webFlow import webFlow
from getInput import getProcessingInput, getJobInput
from processingFlow import processDf
from analysisFlow import analyzeProcessingResult
from reportFlow import generateReport
from time import time
from dataIO import *


def performanceTest():  # remove for production # TEST
	from constand import constand
	""" Use this development method to test the performance of the CONSTANd algorithm. """
	t = []
	for i in range(100):
		params = getProcessingInput()
		df = pd.DataFrame(np.random.uniform(low=10 ** 3, high=10 ** 5, size=(2*10**3, 6)), columns=list('ABCDEF'))
		start = time()
		constand(np.asarray(df), 1e-2, 50)
		stop = time()
		t.append((stop - start))
	print("average runtime: " + str(np.mean(t)))


def isotopicImpuritiesTest(): # TEST
	from constand import constand
	from processing import getIntensities
	## test if isotopic correction is necessary:
	params = getProcessingInput()
	# get the dataframe
	df = importDataFrame(params['files_in'], delim=params['delim_in'], header=params['header_in'])
	correctedIntensities = getIntensities(df)
	normalizedIntensities, convergenceTrail, R, S = constand(correctedIntensities, params['accuracy'],
	                                                         params['maxIterations'])
	# exportData(normalizedIntensities, 'txt', path_out=params['path_out'],
	#            filename=params['jobname'] + '_normalizedIntensities', delim_out=params['delim_out'])
	# test "impure data"
	correctedIntensities_impure = correctedIntensities
	spillover = correctedIntensities_impure[0, :] * 0.1
	correctedIntensities_impure[0, :] -= spillover
	correctedIntensities_impure[1, :] += spillover
	normalizedIntensities_impure, convergenceTrail_i, R_i, S_i = constand(correctedIntensities_impure,
	                                                                      params['accuracy'],
	                                                                      params['maxIterations'])
	diff = abs(normalizedIntensities - normalizedIntensities_impure)
	print(np.allclose(normalizedIntensities, normalizedIntensities_impure, atol=1e-3, equal_nan=True))
	print(np.nanmean(np.nanmean(diff[:, 0:1], 1)))
	print(max(np.amax(diff, 1)))
# False tot en met 1e-3 --> fouten van > 0.1%


def isotopicCorrectionsTest(params): # TEST
	from processing import isotopicCorrection
	if params['isotopicCorrection_bool']:
		int_in = np.array([range(6), range(6)]) + np.array([np.zeros(6), 5*np.ones(6)])
		# perform isotopic corrections but do NOT apply them to df because this information is sensitive (copyright i-TRAQ)
		icm = params['isotopicCorrection_matrix']
		icm[0,0] = 0.9
		icm[0,1] = 0.1
		int_out = isotopicCorrection(int_in, correctionsMatrix=icm)
		print(int_out)
		# M=np.eye(6); M[0,0]=0.9; M[0,1]=0.1; b=np.asarray(range(6)); c=np.asarray(range(6))+5
		# print(int_out) above should be equal to:
		# [np.linalg.solve(M, b) ; np.linalg.solve(M, c)]


def MS2IntensityDoesntMatter(df):
	from processing import getIntensities
	from constand import constand
	I = getIntensities(df)
	r1 = constand(I, 1e-5, 50)
	I[0] *= 1e9 # this is BIG. MS2 intensity doesnt reach beyond 1e9 so if one value has magnitudeOrder 1 it's still OK.
	r2 = constand(I, 1e-5, 50)
	print(np.allclose(r1[0], r2[0], equal_nan=True))
	diff = r1[0] - r2[0]
	maxdiff = max(np.amax(diff, 1))
	print(maxdiff)


def testDataComplementarity(df):
	scannrs_init = set(df.groupby('First Scan').groups.keys())
	main(testing=False, writeToDisk=True)
	# SANITY CHECK if df + removedData scan numbers = total scan numbers.
	scannrs_final = set(df.groupby('First Scan').groups.keys())
	##### THIS IS OUTDATED SINCE COMMIT b98041f
	removedDataLoaded = pickle.load(open('../data/MB_result_removedData', 'rb'))
	for value in removedDataLoaded.values():
		scannrs_final = scannrs_final.union(set(value['First Scan']))
	print(scannrs_final == scannrs_init)


def MAPlot(x,y, title):
	from matplotlib import pyplot as plt
	logx = np.log2(x)
	logy = np.log2(y)
	plt.scatter((logx+logy)*0.5, logx-logy)
	if title is None:
		plt.title('PD2.1 Intensities versus S/N values (scaled relatively within each row/peptide)')
	else:
		plt.title(title)
	plt.xlabel('A')
	plt.ylabel('M')
	plt.show()


def compareIntensitySN(df1, df2):
	from processing import getIntensities
	filepath1 = '../data/COON data/PSMs/BR1_e_ISO.txt'
	filepath2 = '../data/COON data/PSMs/BR1_f_ISO_SN.txt'
	intensityColumns = ["126", "127N", "127C", "128C","129N", "129C", "130C", "131"]
	pickleFileName = 'job/compareIntensitySNProcessingResults'
	constandnorm=True
	alsoprocess=True
	if constandnorm:
		if alsoprocess and os.path.exists(pickleFileName):
			processingResults = pickle.load(open(pickleFileName, 'rb'))
		else:
			params=getProcessingInput('job/processingConfig.ini')
			dfs = []
			if df1 is None and df2 is None:
				for filepath in [filepath1, filepath2]:
					dfs.append(importDataFrame(filepath, delim=params['delim_in'], header=params['header_in']))
			else:
				dfs = [df1, df2]
			if alsoprocess:
				processingResults = [processDf(df, params, writeToDisk=False) for df in dfs]
				pickle.dump(processingResults, open(pickleFileName, 'wb'))
		if alsoprocess:
			relIntensities = getIntensities(processingResults[0][0], intensityColumns=intensityColumns)
			relSNs = getIntensities(processingResults[1][0], intensityColumns=intensityColumns)
		else:
			from constand import constand
			relIntensities, __, __, __ = constand(getIntensities(dfs[0], intensityColumns=intensityColumns), 1e-5, 50)
			relSNs, __, __, __ = constand(getIntensities(dfs[1], intensityColumns=intensityColumns), 1e-5, 50)
	else:
		if df1 is None and df2 is None:
			df1 = importDataFrame(filepath1, delim='\t', header=0)
			df2 = importDataFrame(filepath2, delim='\t', header=0)
		intensityColumns = ["126", "127N", "127C", "128C", "129N", "129C", "130C", "131"]
		relIntensities = np.empty((len(df1.index),8), dtype='float')
		relSNs = np.empty((len(df2.index),8), dtype='float')
		for col in range(len(intensityColumns)):
			relIntensities[:, col] = 1/8*df1.loc[:, intensityColumns[col]]/np.nanmean(df1.loc[:, intensityColumns],1)
			relSNs[:, col] = 1/8*df2.loc[:, intensityColumns[col]]/np.nanmean(df2.loc[:, intensityColumns],1)
	diff = abs(relIntensities - relSNs)
	print(np.allclose(relIntensities, relSNs, atol=1e-3, equal_nan=True))
	print("mean over all values")
	print(np.nanmean(np.nanmean(diff[:, 0:6], 1)))
	print("max difference")
	print(np.nanmax(np.nanmax(diff, 1)))

	MAPlot(relIntensities.reshape(relIntensities.size, 1), relSNs.reshape(relSNs.size, 1))


def devStuff(df, params): # TEST
	# performanceTest()
	# isotopicCorrectionsTest(params)
	# MS2IntensityDoesntMatter(df)
	# testDataComplementarity(df)
	compareIntensitySN(None, None)
	pass


def main(jobConfigFilePath, doProcessing, doAnalysis, doReport, writeToDisk, testing):
	"""
	For now this is just stuff for debugging and testing. Later:
	Contains and explicits the workflow of the program. Using the booleans doProcessing, doAnalysis and writeToDisk one
	can control	which parts of the workflow to perform.
	"""
	logFilePath = os.path.abspath(os.path.join(jobConfigFilePath, os.path.join(os.pardir, 'log.txt')))
	logging.basicConfig(filename=logFilePath, level=logging.INFO)
	start = time()
	jobParams = getJobInput(jobConfigFilePath) # config filenames + params for the combination of experiments
	processingParams = {} # specific params for each experiment
	dfs = {}
	processingResults = {}
	experimentNames = list(jobParams['schema'].keys())

	if not testing:
		for eName in experimentNames:
			""" Data processing """
			# get all input parameters
			processingParams[eName] = getProcessingInput(jobParams['schema'][eName]['config'])
			# get the dataframes
			dfs[eName] = getData(processingParams[eName]['data'], delim=processingParams[eName]['delim_in'],
			                     header=processingParams[eName]['header_in'],
			                     wrapper=processingParams[eName]['wrapper'])
			processing_path_out = processingParams[eName]['path_out']
			processingResultsDumpFilename = os.path.join(processing_path_out, 'processingResultsDump_'+str(eName))
			if doProcessing:
				print('Starting processing of ' + eName + '...')
				# prepare the output directories
				if not os.path.exists(processing_path_out):  # do not overwrite dir
					assert os.path.exists(
						os.path.abspath(os.path.join(processing_path_out, os.path.pardir)))  # parent dir must exist
					os.makedirs(processing_path_out)
				else:
					raise Exception("Output path "+processing_path_out+" already exists! Aborting.")

				# process every input dataframe
				logging.info("Starting processing of experiment '" + eName + "' of job '" + jobParams['jobname'] + "' at " +
			             str(datetime.datetime.now()).split('.')[0])
				processingResults[eName] = processDf(dfs[eName], processingParams[eName], writeToDisk)
				logging.info("Finished processing of experiment '" + eName + "' of job '" + jobParams['jobname'] + "' at " +
			             str(datetime.datetime.now()).split('.')[0])
				pickle.dump(processingResults[eName], open(processingResultsDumpFilename, 'wb')) # TEST
			elif doAnalysis:
				try:
					processingResults[eName] = pickle.load(open(processingResultsDumpFilename, 'rb'))
				except FileNotFoundError:
					raise FileNotFoundError("There is no previously processed data in this path: "+processingResultsDumpFilename)
			else:
				logging.warning("No processing step performed nor processing file loaded for experiment "+str(eName)+"!")

		""" Data analysis """
		analysis_path_out = jobParams['path_out']
		analysisResultsDumpFilename = os.path.join(analysis_path_out, 'analysisResultsDump')
		if doAnalysis:
			print('Starting analysis...')
			# prepare the output directories
			if not os.path.exists(analysis_path_out):  # do not overwrite dir
				assert os.path.exists(os.path.abspath(os.path.join(analysis_path_out, os.path.pardir)))  # parent dir must exist
				os.makedirs(analysis_path_out)

			# perform analysis
			logging.info("Starting analysis of job: " + jobParams['jobname'] + "at " +
			             str(datetime.datetime.now()).split('.')[0])
			analysisResults = analyzeProcessingResult(processingResults, jobParams, writeToDisk)
			logging.info("Finished analysis of job: " + jobParams['jobname'] + "at " +
			             str(datetime.datetime.now()).split('.')[0])
			pickle.dump(analysisResults, open(analysisResultsDumpFilename, 'wb'))  # TEST
		elif doReport:
			try:
				analysisResults = pickle.load(open(analysisResultsDumpFilename, 'rb'))
			except FileNotFoundError:
				raise FileNotFoundError("There is no previously analyzed data in this path: "+analysisResultsDumpFilename)
		else:
			logging.warning("No analysis step performed nor analysis file loaded!")

		""" Visualize and generate report """
		results_path_out = jobParams['path_results']

		if doReport:
			print('Starting visualization and report generation...')
			# prepare the output directories
			if not os.path.exists(results_path_out):  # do not overwrite dir
				assert os.path.exists(os.path.abspath(os.path.join(results_path_out, os.path.pardir)))  # parent dir must exist
				os.makedirs(results_path_out)

			# visualize and make a report
			logging.info("Starting visualization end report generation of job: " + jobParams['jobname'] + "at " +
			             str(datetime.datetime.now()).split('.')[0])
			generateReport(analysisResults, jobParams, logFilePath, writeToDisk)
			logging.info("Finished visualization end report generation of job: " + jobParams['jobname'] + "at " +
			             str(datetime.datetime.now()).split('.')[0])
		else:
			logging.warning("No report generated!")

	elif testing:
		devStuff(dfs, processingParams)
	stop = time()
	print(stop - start)


if __name__ == '__main__':
	masterConfigFilePath = 'job/jobConfig.ini' # TEST
	#masterConfigFilePath = webFlow(exptype='COON')
	#masterConfigFilePath = webFlow(exptype='COON', previousjobdirName='2016-12-12 22:37:48.458146_COON')
	#masterConfigFilePath = webFlow(exptype='COON_SN')
	#masterConfigFilePath = webFlow(exptype='COON_SN', previousjobdirName='2016-12-12 22:41:02.295891_COON_SN')
	#masterConfigFilePath = webFlow(exptype='COON_norm') # todo constand uitzetten
	#masterConfigFilePath = webFlow(exptype='COON_norm', previousjobdirName='2016-12-12 22:43:38.030716_COON_norm')  # todo constand uitzetten
	#masterConfigFilePath = webFlow(exptype='COON_SN_norm')  # todo constand uitzetten
	#masterConfigFilePath = webFlow(exptype='COON_SN_norm', previousjobdirName='2016-12-12 22:48:30.701250_COON_SN_norm')  # todo constand uitzetten
	#masterConfigFilePath = webFlow(exptype='COON_nonormnoconstand')  # todo constand uitzetten

	sys.exit(main(jobConfigFilePath=masterConfigFilePath, doProcessing=False, doAnalysis=False, doReport=True,
	              testing=False, writeToDisk=True))
