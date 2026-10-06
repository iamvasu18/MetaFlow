import {
  ArrowRight,
  Check,
  ChevronRight,
  Cloud,
  Database,
  FileSpreadsheet,
  Upload,
  X,
} from "lucide-react";
import { useRef, useState } from "react";

const STEPS = ["Source", "Upload", "Map Fields", "Import", "Results"];

function Import() {
  const fileInputRef = useRef(null);

  const [currentStep, setCurrentStep] = useState(0);
  const [selectedSource, setSelectedSource] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleSourceSelect = (source) => {
    if (source !== "file") return;

    setSelectedSource("file");
    fileInputRef.current?.click();
  };

  const handleFile = (file) => {
    if (!file) return;

    const validExtensions = [
      ".csv",
      ".xlsx",
      ".xls",
    ];

    const extension = file.name
      .slice(file.name.lastIndexOf("."))
      .toLowerCase();

    if (!validExtensions.includes(extension)) {
      alert("Please upload a CSV, XLSX, or XLS file.");
      return;
    }

    setSelectedFile(file);
    setSelectedSource("file");
    setCurrentStep(1);
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (file) {
      handleFile(file);
    }

    event.target.value = "";
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragActive(false);

    const file = event.dataTransfer.files?.[0];

    if (file) {
      handleFile(file);
    }
  };

  const removeFile = () => {
    setSelectedFile(null);
    setCurrentStep(0);
  };

  const goToMapping = () => {
    if (!selectedFile) return;
    setCurrentStep(2);
  };

  const goToImport = () => {
    setCurrentStep(3);
  };

  const completeImport = () => {
    setCurrentStep(4);
  };

  return (
    <main className="min-h-[calc(100vh-64px)] bg-slate-50 text-slate-900">
      {/* =====================================================
          PAGE HEADER
      ===================================================== */}

      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-[1180px] px-6 py-7">

          <div>
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">
              Import Data
            </h1>

            <p className="mt-1 text-[14px] text-slate-500">
              Import records into your Salesforce organization
            </p>
          </div>

          {/* =================================================
              STEPPER
          ================================================= */}

          <div className="mt-6 flex items-center">

            {STEPS.map((step, index) => {
              const completed = index < currentStep;
              const active = index === currentStep;

              return (
                <div
                  key={step}
                  className="flex items-center"
                >
                  <div
                    className={[
                      "flex items-center gap-2 rounded-full px-3 py-1.5 text-[12px] font-medium transition",
                      active
                        ? "bg-blue-50 text-blue-600"
                        : completed
                        ? "text-blue-600"
                        : "text-slate-500",
                    ].join(" ")}
                  >
                    {completed ? (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white">
                        <Check size={11} />
                      </span>
                    ) : (
                      <span
                        className={[
                          "flex h-5 w-5 items-center justify-center rounded-full border text-[9px]",
                          active
                            ? "border-blue-500 bg-blue-600 text-white"
                            : "border-slate-300 text-slate-400",
                        ].join(" ")}
                      >
                        {index + 1}
                      </span>
                    )}

                    {step}
                  </div>

                  {index < STEPS.length - 1 && (
                    <div className="mx-2 h-px w-8 bg-slate-200" />
                  )}
                </div>
              );
            })}

          </div>
        </div>
      </div>

      {/* =====================================================
          CONTENT
      ===================================================== */}

      <div className="mx-auto max-w-[1180px] px-6 py-8">

        {currentStep === 0 && (
          <SourceStep
            onSelect={handleSourceSelect}
          />
        )}

        {currentStep === 1 && (
          <UploadStep
            file={selectedFile}
            dragActive={dragActive}
            setDragActive={setDragActive}
            onDrop={handleDrop}
            onChoose={() => fileInputRef.current?.click()}
            onRemove={removeFile}
            onContinue={goToMapping}
          />
        )}

        {currentStep === 2 && (
          <MappingStep
            file={selectedFile}
            onBack={() => setCurrentStep(1)}
            onContinue={goToImport}
          />
        )}

        {currentStep === 3 && (
          <ImportStep
            file={selectedFile}
            onBack={() => setCurrentStep(2)}
            onComplete={completeImport}
          />
        )}

        {currentStep === 4 && (
          <ResultsStep
            file={selectedFile}
            onNewImport={() => {
              setSelectedFile(null);
              setSelectedSource(null);
              setCurrentStep(0);
            }}
          />
        )}

      </div>

      {/* Hidden file input */}

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={handleFileChange}
      />
    </main>
  );
}


/* =========================================================
   SOURCE STEP
========================================================= */

function SourceStep({ onSelect }) {
  return (
    <section>

      <div className="mb-5">
        <h2 className="text-[18px] font-semibold text-slate-900">
          Choose Data Source
        </h2>

        <p className="mt-1 text-[12px] text-slate-500">
          Select where your Salesforce records are coming from.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">

        {/* CSV / EXCEL */}

        <SourceCard
          icon={FileSpreadsheet}
          title="CSV / Excel"
          description="Upload .csv, .xlsx, or .xls files"
          active
          onClick={() => onSelect("file")}
        />

        {/* SALESFORCE ORG */}

        <SourceCard
          icon={Cloud}
          title="Another Salesforce Org"
          description="Export from one org and import to another"
          disabled
        />

        {/* DATABASE */}

        <SourceCard
          icon={Database}
          title="Database"
          description="Import from an external database"
          disabled
        />

      </div>

      {/* Information */}

      <div className="mt-6 rounded-xl border border-blue-100 bg-blue-50/60 px-5 py-4">

        <div className="flex items-start gap-3">

          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-blue-600">
            <FileSpreadsheet size={16} />
          </div>

          <div>
            <p className="text-[11px] font-semibold text-slate-800">
              CSV / Excel import
            </p>

            <p className="mt-1 text-[10px] leading-5 text-slate-500">
              Upload your Salesforce data file and ApexAI will help
              you review the records, map source fields to Salesforce
              fields, validate the data and prepare the import.
            </p>
          </div>

        </div>

      </div>

    </section>
  );
}


/* =========================================================
   SOURCE CARD
========================================================= */

function SourceCard({
  icon: Icon,
  title,
  description,
  active,
  disabled,
  onClick,
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={[
        "group relative min-h-[190px] rounded-xl border bg-white p-6 text-left transition",
        active
          ? "border-slate-300 hover:-translate-y-0.5 hover:border-blue-400 hover:shadow-md"
          : "border-slate-200",
        disabled
          ? "cursor-not-allowed opacity-55"
          : "cursor-pointer",
      ].join(" ")}
    >

      {/* Arrow */}

      {!disabled && (
        <ChevronRight
          size={16}
          className="absolute right-5 top-5 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-blue-500"
        />
      )}

      {/* Icon */}

      <div
        className={[
          "flex h-11 w-11 items-center justify-center rounded-xl",
          active
            ? "bg-blue-50 text-blue-600"
            : "bg-slate-50 text-slate-400",
        ].join(" ")}
      >
        <Icon size={22} strokeWidth={1.8} />
      </div>

      {/* Content */}

      <h3 className="mt-5 text-[15px] font-semibold text-slate-900">
        {title}
      </h3>

      <p className="mt-2 max-w-[250px] text-[11px] leading-5 text-slate-500">
        {description}
      </p>

      {disabled && (
        <span className="mt-3 inline-block text-[10px] font-medium text-amber-500">
          Coming soon
        </span>
      )}

      {active && (
        <span className="mt-4 inline-flex items-center gap-1 text-[10px] font-semibold text-blue-600">
          Choose source
          <ArrowRight size={12} />
        </span>
      )}

    </button>
  );
}


/* =========================================================
   UPLOAD STEP
========================================================= */

function UploadStep({
  file,
  dragActive,
  setDragActive,
  onDrop,
  onChoose,
  onRemove,
  onContinue,
}) {
  return (
    <section className="mx-auto max-w-[850px]">

      <div className="mb-5">
        <h2 className="text-[18px] font-semibold">
          Upload Your File
        </h2>

        <p className="mt-1 text-[12px] text-slate-500">
          Upload the CSV or Excel file containing the records.
        </p>
      </div>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        className={[
          "rounded-2xl border-2 border-dashed bg-white p-12 text-center transition",
          dragActive
            ? "border-blue-500 bg-blue-50/50"
            : "border-slate-200",
        ].join(" ")}
      >

        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
          <Upload size={25} />
        </div>

        <h3 className="mt-5 text-[15px] font-semibold">
          Drop your file here
        </h3>

        <p className="mt-2 text-[11px] text-slate-500">
          or choose a CSV, XLSX, or XLS file from your computer
        </p>

        <button
          type="button"
          onClick={onChoose}
          className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[11px] font-semibold text-white shadow-sm transition hover:bg-blue-700"
        >
          <Upload size={14} />
          Choose File
        </button>

      </div>

      {file && (
        <div className="mt-4 flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">

          <div className="flex min-w-0 items-center gap-3">

            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-green-50 text-green-600">
              <FileSpreadsheet size={16} />
            </div>

            <div className="min-w-0">
              <p className="truncate text-[11px] font-semibold text-slate-800">
                {file.name}
              </p>

              <p className="mt-0.5 text-[9px] text-slate-400">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>

          </div>

          <button
            type="button"
            onClick={onRemove}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-500"
          >
            <X size={14} />
          </button>

        </div>
      )}

      <div className="mt-5 flex justify-end">

        <button
          type="button"
          disabled={!file}
          onClick={onContinue}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue
          <ArrowRight size={13} />
        </button>

      </div>

    </section>
  );
}


/* =========================================================
   MAPPING STEP
========================================================= */

function MappingStep({
  file,
  onBack,
  onContinue,
}) {
  const mappings = [
    {
      source: "First Name",
      target: "FirstName",
      status: "Matched",
    },
    {
      source: "Last Name",
      target: "LastName",
      status: "Matched",
    },
    {
      source: "Email",
      target: "Email",
      status: "Matched",
    },
    {
      source: "Phone",
      target: "Phone",
      status: "Matched",
    },
  ];

  return (
    <section>

      <div className="mb-5 flex items-end justify-between">

        <div>
          <h2 className="text-[18px] font-semibold">
            Map Fields
          </h2>

          <p className="mt-1 text-[12px] text-slate-500">
            Map your source columns to Salesforce fields.
          </p>
        </div>

        <span className="text-[10px] text-slate-400">
          {file?.name}
        </span>

      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">

        <div className="grid grid-cols-3 border-b border-slate-200 bg-slate-50 px-5 py-3">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Source Field
          </span>

          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Salesforce Field
          </span>

          <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
            Status
          </span>
        </div>

        {mappings.map((mapping) => (
          <div
            key={mapping.source}
            className="grid grid-cols-3 items-center border-b border-slate-100 px-5 py-4 last:border-b-0"
          >
            <span className="text-[11px] text-slate-700">
              {mapping.source}
            </span>

            <span className="text-[11px] text-slate-700">
              {mapping.target}
            </span>

            <span className="inline-flex w-fit items-center gap-1 rounded-full bg-green-50 px-2 py-1 text-[9px] font-medium text-green-600">
              <Check size={10} />
              {mapping.status}
            </span>
          </div>
        ))}

      </div>

      <div className="mt-5 flex justify-between">

        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-slate-200 px-4 py-2.5 text-[10px] font-medium text-slate-600 hover:bg-slate-50"
        >
          Back
        </button>

        <button
          type="button"
          onClick={onContinue}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[10px] font-semibold text-white hover:bg-blue-700"
        >
          Continue
          <ArrowRight size={13} />
        </button>

      </div>

    </section>
  );
}


/* =========================================================
   IMPORT STEP
========================================================= */

function ImportStep({
  file,
  onBack,
  onComplete,
}) {
  return (
    <section className="mx-auto max-w-[850px]">

      <div className="mb-5">
        <h2 className="text-[18px] font-semibold">
          Ready to Import
        </h2>

        <p className="mt-1 text-[12px] text-slate-500">
          Review your import configuration before sending records
          to Salesforce.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6">

        <div className="flex items-center gap-3">

          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <FileSpreadsheet size={18} />
          </div>

          <div>
            <p className="text-[12px] font-semibold">
              {file?.name}
            </p>

            <p className="mt-0.5 text-[9px] text-slate-400">
              Salesforce record import
            </p>
          </div>

        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-3">

          <SummaryItem
            label="Source"
            value="CSV / Excel"
          />

          <SummaryItem
            label="Destination"
            value="Salesforce"
          />

          <SummaryItem
            label="Validation"
            value="Ready"
          />

        </div>

      </div>

      <div className="mt-5 flex justify-between">

        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-slate-200 px-4 py-2.5 text-[10px] font-medium text-slate-600 hover:bg-slate-50"
        >
          Back
        </button>

        <button
          type="button"
          onClick={onComplete}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[10px] font-semibold text-white hover:bg-blue-700"
        >
          Start Import
          <ArrowRight size={13} />
        </button>

      </div>

    </section>
  );
}


/* =========================================================
   SUMMARY ITEM
========================================================= */

function SummaryItem({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
      <p className="text-[9px] uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-[11px] font-semibold text-slate-700">
        {value}
      </p>
    </div>
  );
}


/* =========================================================
   RESULTS STEP
========================================================= */

function ResultsStep({
  file,
  onNewImport,
}) {
  return (
    <section className="mx-auto max-w-[850px]">

      <div className="rounded-2xl border border-green-100 bg-white p-10 text-center">

        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-50 text-green-600">
          <Check size={26} />
        </div>

        <h2 className="mt-5 text-[20px] font-semibold">
          Import Complete
        </h2>

        <p className="mx-auto mt-2 max-w-[500px] text-[11px] leading-5 text-slate-500">
          The import process for{" "}
          <span className="font-medium text-slate-700">
            {file?.name}
          </span>{" "}
          has completed successfully.
        </p>

        <div className="mx-auto mt-7 grid max-w-[550px] gap-3 sm:grid-cols-3">

          <ResultItem
            label="Records"
            value="4,200"
          />

          <ResultItem
            label="Imported"
            value="4,185"
          />

          <ResultItem
            label="Errors"
            value="15"
          />

        </div>

        <button
          type="button"
          onClick={onNewImport}
          className="mt-7 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-[10px] font-semibold text-white hover:bg-blue-700"
        >
          Start New Import
          <ArrowRight size={13} />
        </button>

      </div>

    </section>
  );
}


/* =========================================================
   RESULT ITEM
========================================================= */

function ResultItem({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
      <p className="text-[9px] uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-[17px] font-semibold text-slate-800">
        {value}
      </p>
    </div>
  );
}

export default Import;