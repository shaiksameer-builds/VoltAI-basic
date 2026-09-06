import React, { useState } from 'react';
import { X, UploadCloud, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { VoltAIAPI } from '../services/api';

export default function CSVUploadModal({ isOpen, onClose, onSuccess }) {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const res = await VoltAIAPI.uploadCSV(file);
      setResult(res);
      if (onSuccess) onSuccess();
    } catch (err) {
      setError(err.message || 'CSV Ingestion failed');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="glass-card max-w-md w-full p-6 border border-slate-700 relative shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-lg font-bold text-white flex items-center gap-2 mb-1">
          <UploadCloud className="w-5 h-5 text-emerald-400" />
          Ingest Telemetry CSV
        </h3>
        <p className="text-xs text-slate-400 mb-4">
          Upload a canonical telemetry CSV file containing interval readings.
        </p>

        {/* Upload Zone */}
        <div className="border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-xl p-6 flex flex-col items-center justify-center text-center transition-colors bg-dark-900/50">
          <UploadCloud className="w-10 h-10 text-emerald-400/80 mb-2" />
          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
            id="csv-file-input"
          />
          <label
            htmlFor="csv-file-input"
            className="cursor-pointer text-xs font-semibold text-emerald-400 hover:text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg mb-1"
          >
            Select CSV File
          </label>
          <span className="text-[11px] text-slate-500">
            {file ? file.name : 'or drag & drop file here'}
          </span>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs text-rose-400 flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Success Alert */}
        {result && (
          <div className="mt-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs text-emerald-400 flex items-start space-x-2">
            <CheckCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">{result.message || 'CSV Ingestion Successful'}</p>
              {result.data && (
                <span className="text-[11px] text-emerald-300/80 block mt-0.5">
                  Processed: {result.data.rows_processed} | Inserted: {result.data.rows_inserted}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Modal Actions */}
        <div className="mt-6 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-dark-700 hover:bg-dark-600 text-slate-300 text-xs font-medium rounded-lg transition-colors"
          >
            Close
          </button>

          <button
            onClick={handleUpload}
            disabled={!file || isUploading}
            className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow-md shadow-emerald-600/20 transition-all"
          >
            {isUploading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
            <span>{isUploading ? 'Ingesting...' : 'Start Ingestion'}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
