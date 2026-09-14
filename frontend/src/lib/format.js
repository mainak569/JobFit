const numberFormat = new Intl.NumberFormat("en-IN");
const dateFormat = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });

export function formatNumber(value) {
  return numberFormat.format(value);
}

export function formatDate(isoString) {
  return dateFormat.format(new Date(isoString));
}

export function jobLabel(jobDescription) {
  return jobDescription.title || "Untitled job";
}

export const CATEGORY_LABELS = {
  languages: "Languages",
  frontend: "Frontend",
  backend: "Backend",
  databases: "Databases",
  devops: "DevOps & Tools",
  concepts: "Concepts",
};
