import {
  FileText,
  UploadCloud,
  X
} from "lucide-react";

import {
  useRef,
  useState
} from "react";

export default function UploadDropzone({
  file,
  onChange
}: {
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  const inputRef =
    useRef<HTMLInputElement>(null);

  const [drag, setDrag] =
    useState(false);

  const accept = (candidate?: File) => {
    if (!candidate) return;

    if (
      !candidate.name
        .toLowerCase()
        .endsWith(".dxf")
    ) {
      window.alert(
        "Для расчёта требуется файл DXF (.dxf)."
      );

      return;
    }

    onChange(candidate);
  };

  return (
    <div
      className={`dropzone ${
        drag ? "dragging" : ""
      } ${file ? "has-file" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() =>
        setDrag(false)
      }
      onDrop={(event) => {
        event.preventDefault();
        setDrag(false);

        accept(
          event.dataTransfer.files[0]
        );
      }}
      onClick={() =>
        inputRef.current?.click()
      }
      role="button"
      tabIndex={0}
      aria-label="Загрузить DXF"
      onKeyDown={(event) => {
        if (
          event.key === "Enter" ||
          event.key === " "
        ) {
          inputRef.current?.click();
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".dxf"
        hidden
        onChange={(event) =>
          accept(
            event.target.files?.[0]
          )
        }
      />

      {file ? (
        <div
          className="selected-file"
          onClick={(event) =>
            event.stopPropagation()
          }
        >
          <div className="file-icon">
            <FileText size={24} />
          </div>

          <div className="file-info">
            <strong>
              {file.name}
            </strong>

            <span>
              {(file.size / 1024).toFixed(1)}
              {" КБ · DXF"}
            </span>
          </div>

          <button
            className="icon-button"
            type="button"
            onClick={() =>
              onChange(null)
            }
            aria-label="Удалить файл"
          >
            <X size={18} />
          </button>
        </div>
      ) : (
        <>
          <div className="upload-icon">
            <UploadCloud size={30} />
          </div>

          <strong>
            Перетащите DXF сюда
          </strong>

          <span>
            или нажмите, чтобы выбрать файл
          </span>

          <small>
            Поддерживается формат .dxf
          </small>
        </>
      )}
    </div>
  );
}