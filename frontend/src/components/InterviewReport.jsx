import ScoreGauge from "./ScoreGauge.jsx";

const SCALE = [1, 2, 3, 4, 5];

function Rating({ score }) {
  return (
    <span className="rating" role="img" aria-label={`Scored ${score} out of 5`}>
      {SCALE.map((step) => (
        <span key={step} className={step <= score ? "rating__dot rating__dot--on" : "rating__dot"} aria-hidden="true" />
      ))}
      <span className="rating__value" aria-hidden="true">
        {score}/5
      </span>
    </span>
  );
}

function FeedbackList({ title, items }) {
  if (items.length === 0) return null;
  return (
    <div className="report-card__list">
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function InterviewReport({ session }) {
  const { report, overall_score: score } = session;

  return (
    <section className="report" aria-labelledby="report-heading">
      <h2 id="report-heading" tabIndex={-1}>
        Your feedback
      </h2>
      <div className="score-row">
        {score !== null && <ScoreGauge score={score} label="Interview score" />}
        <p className="report__summary">{report.summary}</p>
      </div>

      <ol className="report__questions">
        {report.questions.map((question) => (
          <li key={question.index} className="report-card">
            <div className="report-card__head">
              <h3>
                Question {question.index + 1}
                {question.focus && <span className="report-card__focus"> · {question.focus}</span>}
              </h3>
              <Rating score={question.score} />
            </div>
            <p className="report-card__question">{question.question}</p>
            <FeedbackList title="What worked" items={question.strengths} />
            <FeedbackList title="To improve" items={question.improvements} />
            {question.better_answer && (
              <details className="report-card__better">
                <summary>What a strong answer covers</summary>
                <p>{question.better_answer}</p>
              </details>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
