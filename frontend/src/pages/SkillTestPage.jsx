import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getTestStatus, startTest, submitTest } from "../api/skillTestApi";
import VerifiedBadge from "../components/VerifiedBadge";
import "../components/SkillTest.css";

const LEVEL_LABEL = {
  BEGINNER: "Beginner",
  INTERMEDIATE: "Intermediate",
  ADVANCED: "Advanced",
};
const LETTERS = ["A", "B", "C", "D"];
const SKILLS_PAGE = "/skills"; // change if your "My Skills" route is different

const levelLabel = (level) => LEVEL_LABEL[level] || level;

function formatClock(totalSeconds) {
  const s = Math.max(0, totalSeconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function formatDateTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function messageFrom(err, fallback) {
  return err?.response?.data?.message || err?.response?.data?.detail || fallback;
}

const answersKey = (testId) => `skilltest-answers-${testId}`;

function loadSavedAnswers(testId) {
  try {
    return JSON.parse(sessionStorage.getItem(answersKey(testId))) || {};
  } catch {
    return {};
  }
}

export default function SkillTestPage() {
  const { skillId } = useParams();

  // loading | intro | preparing | testing | submitting | result | error
  const [phase, setPhase] = useState("loading");
  const [status, setStatus] = useState(null);
  const [test, setTest] = useState(null);
  const [answers, setAnswers] = useState({}); // questionId -> option key
  const [current, setCurrent] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const deadlineRef = useRef(0);
  const submittingRef = useRef(false);
  const answersRef = useRef(answers);
  answersRef.current = answers;

  useEffect(() => {
    let active = true;
    getTestStatus(skillId)
      .then((data) => {
        if (!active) return;
        setStatus(data);
        setPhase("intro");
      })
      .catch((err) => {
        if (!active) return;
        setError(messageFrom(err, "This skill couldn't be loaded."));
        setPhase("error");
      });
    return () => {
      active = false;
    };
  }, [skillId]);

  const begin = async () => {
    setError("");
    setPhase("preparing");
    try {
      const data = await startTest(skillId);
      deadlineRef.current = Date.now() + data.secondsRemaining * 1000;
      submittingRef.current = false;
      setTest(data);
      setAnswers(loadSavedAnswers(data.testId));
      setSecondsLeft(data.secondsRemaining);
      setCurrent(0);
      setPhase("testing");
    } catch (err) {
      setError(messageFrom(err, "The test couldn't be started. Try again in a minute."));
      setPhase("intro");
    }
  };

  const finish = useCallback(async () => {
    if (!test || submittingRef.current) return;
    submittingRef.current = true;
    setPhase("submitting");
    const payload = test.questions.map((q) => ({
      questionId: q.questionId,
      selectedKey: answersRef.current[q.questionId] ?? null,
    }));
    try {
      const data = await submitTest(test.testId, payload);
      try {
        sessionStorage.removeItem(answersKey(test.testId));
      } catch {
        /* storage unavailable: nothing to clean up */
      }
      setResult(data);
      setPhase("result");
      window.scrollTo({ top: 0 });
    } catch (err) {
      submittingRef.current = false;
      setError(messageFrom(err, "Your answers weren't sent. Check your connection and submit again."));
      setPhase("testing");
    }
  }, [test]);

  // Countdown based on a fixed deadline, so it stays accurate if the tab sleeps.
  useEffect(() => {
    if (phase !== "testing") return undefined;
    const tick = () => {
      const left = Math.round((deadlineRef.current - Date.now()) / 1000);
      setSecondsLeft(left);
      if (left <= 0) finish();
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [phase, finish]);

  // Keep answers across an accidental refresh (the server keeps the timer).
  useEffect(() => {
    if (!test || phase !== "testing") return;
    try {
      sessionStorage.setItem(answersKey(test.testId), JSON.stringify(answers));
    } catch {
      /* storage unavailable: answers stay in memory only */
    }
  }, [answers, test, phase]);

  const choose = (questionId, key) => setAnswers((prev) => ({ ...prev, [questionId]: key }));

  const confirmAndFinish = () => {
    const unanswered = test.questions.filter((q) => answers[q.questionId] === undefined).length;
    if (
      unanswered > 0 &&
      !window.confirm(
        `${unanswered} question${unanswered === 1 ? " is" : "s are"} unanswered and will be marked wrong. Submit anyway?`
      )
    ) {
      return;
    }
    finish();
  };

  // ---------------------------------------------------------------- render

  if (phase === "loading") {
    return <Shell><p className="st-muted">Loading…</p></Shell>;
  }

  if (phase === "error") {
    return (
      <Shell>
        <div className="st-panel">
          <p className="st-error" role="alert">{error}</p>
          <Link className="st-btn st-btn-quiet" to={SKILLS_PAGE}>Back to my skills</Link>
        </div>
      </Shell>
    );
  }

  if (phase === "intro" || phase === "preparing") {
    return (
      <Shell>
        <Intro status={status} preparing={phase === "preparing"} error={error} onStart={begin} />
      </Shell>
    );
  }

  if (phase === "result" && result) {
    return <Shell><Result result={result} /></Shell>;
  }

  // testing / submitting
  const question = test.questions[current];
  const total = test.questions.length;
  const answeredCount = test.questions.filter((q) => answers[q.questionId] !== undefined).length;
  const fraction = Math.max(0, Math.min(1, secondsLeft / test.durationSeconds));
  const lowTime = secondsLeft <= 60;
  const isLast = current === total - 1;
  const busy = phase === "submitting";

  return (
    <Shell>
      <div className="st-test-head">
        <div>
          <h1 className="st-title">{test.skillName}</h1>
          <p className="st-muted">{levelLabel(test.level)} test, {answeredCount} of {total} answered</p>
        </div>
        <div className={`st-clock${lowTime ? " is-low" : ""}`} role="timer" aria-live={lowTime ? "polite" : "off"}>
          <span className="st-clock-value">{formatClock(secondsLeft)}</span>
          <span className="st-clock-label">left</span>
        </div>
      </div>

      <div className="st-timebar" aria-hidden="true">
        <div className={`st-timebar-fill${lowTime ? " is-low" : ""}`} style={{ transform: `scaleX(${fraction})` }} />
      </div>

      <nav className="st-steps" aria-label="Questions">
        {test.questions.map((q, i) => {
          const done = answers[q.questionId] !== undefined;
          return (
            <button
              key={q.questionId}
              type="button"
              className={`st-step${i === current ? " is-current" : ""}${done ? " is-done" : ""}`}
              onClick={() => setCurrent(i)}
              aria-current={i === current ? "step" : undefined}
              aria-label={`Question ${i + 1}${done ? ", answered" : ""}`}
              disabled={busy}
            >
              {i + 1}
            </button>
          );
        })}
      </nav>

      <section className="st-panel st-question" aria-labelledby="st-question-text">
        <p className="st-question-count">Question {current + 1} of {total}</p>
        <p id="st-question-text" className="st-question-text">{question.question}</p>

        <div className="st-options" role="radiogroup" aria-labelledby="st-question-text">
          {question.options.map((option, i) => {
            const selected = answers[question.questionId] === option.key;
            return (
              <button
                key={option.key}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`st-option${selected ? " is-selected" : ""}`}
                onClick={() => choose(question.questionId, option.key)}
                disabled={busy}
              >
                <span className="st-option-letter" aria-hidden="true">{LETTERS[i]}</span>
                <span className="st-option-text">{option.text}</span>
              </button>
            );
          })}
        </div>
      </section>

      {error && <p className="st-error" role="alert">{error}</p>}

      <div className="st-nav">
        <button
          type="button"
          className="st-btn st-btn-quiet"
          onClick={() => setCurrent((c) => c - 1)}
          disabled={current === 0 || busy}
        >
          Previous
        </button>
        <div className="st-nav-right">
          {!isLast && (
            <button type="button" className="st-btn st-btn-quiet" onClick={() => setCurrent((c) => c + 1)} disabled={busy}>
              Next
            </button>
          )}
          <button
            type="button"
            className={`st-btn ${isLast ? "st-btn-primary" : "st-btn-outline"}`}
            onClick={confirmAndFinish}
            disabled={busy}
          >
            {busy ? "Submitting…" : "Submit test"}
          </button>
        </div>
      </div>
    </Shell>
  );
}

function Shell({ children }) {
  return <main className="st-page">{children}</main>;
}

function Intro({ status, preparing, error, onStart }) {
  const level = levelLabel(status.level);
  const fullyVerified = status.verified && status.verifiedLevel === status.level;
  const minutes = Math.round(status.durationSeconds / 60);
  const lowerLevel =
    status.level === "ADVANCED" ? "Intermediate" : status.level === "INTERMEDIATE" ? "Beginner" : null;

  return (
    <>
      <Link className="st-back" to={SKILLS_PAGE}>Back to my skills</Link>
      <h1 className="st-title st-title-lg">Verify your {status.skillName} skill</h1>
      <p className="st-lead">
        You listed {status.skillName} at {level} level. Pass a short test to show a verified badge on your
        profile. Verified skills are shown first when people search for partners.
      </p>

      {status.verified && (
        <p className="st-current">
          Current: <VerifiedBadge level={status.verifiedLevel} score={status.verificationScore} />
        </p>
      )}

      <div className="st-panel">
        <dl className="st-facts">
          <div><dt>Questions</dt><dd>{status.questionsPerTest} multiple choice</dd></div>
          <div><dt>Time</dt><dd>{minutes} minutes, submits automatically</dd></div>
          <div>
            <dt>To verify</dt>
            <dd>
              {status.passScore}% or more verifies {level}.
              {lowerLevel && ` ${status.partialScore}–${status.passScore - 1}% verifies ${lowerLevel}.`}
            </dd>
          </div>
          <div><dt>Retakes</dt><dd>One attempt every 24 hours</dd></div>
        </dl>

        {error && <p className="st-error" role="alert">{error}</p>}

        {fullyVerified ? (
          <p className="st-note">This skill is already verified at {level}. Change its level on the Skills page to take a harder test.</p>
        ) : !status.canStart ? (
          <p className="st-note">Your next attempt opens {formatDateTime(status.retryAvailableAt)}.</p>
        ) : (
          <button type="button" className="st-btn st-btn-primary st-btn-wide" onClick={onStart} disabled={preparing}>
            {preparing ? "Preparing your questions…" : status.testInProgress ? "Resume test" : "Start test"}
          </button>
        )}

        {preparing && (
          <p className="st-muted st-small" aria-live="polite">
            The first test for a skill takes up to 30 seconds while questions are written.
          </p>
        )}
      </div>
    </>
  );
}

function Result({ result }) {
  const claimed = levelLabel(result.claimedLevel);
  const verified = result.verifiedLevel ? levelLabel(result.verifiedLevel) : null;
  const tone =
    result.status === "PASSED" && result.verifiedLevel === result.claimedLevel
      ? "good"
      : result.status === "PASSED"
      ? "partial"
      : "bad";

  let headline;
  let detail;
  if (result.status === "EXPIRED") {
    headline = "Time ran out";
    detail = "The test wasn't submitted before the timer ended, so it counts as an attempt.";
  } else if (tone === "good") {
    headline = `${result.skillName} verified at ${claimed}`;
    detail = "Your badge now shows on your profile and in search results.";
  } else if (tone === "partial") {
    headline = `${result.skillName} verified at ${verified}`;
    detail = `You need 80% or more to verify ${claimed}.`;
  } else {
    headline = "Not verified this time";
    detail = "Review the answers below, then try again.";
  }

  return (
    <>
      <div className={`st-result st-result-${tone}`}>
        <div className="st-score">
          <span className="st-score-value">{result.score}%</span>
          <span className="st-score-label">{result.correctCount} of {result.totalQuestions} correct</span>
        </div>
        <div className="st-result-text">
          <h1 className="st-title">{headline}</h1>
          <p>{detail}</p>
          {result.retryAvailableAt && (
            <p className="st-muted">Next attempt opens {formatDateTime(result.retryAvailableAt)}.</p>
          )}
          {verified && <VerifiedBadge level={result.verifiedLevel} score={result.score} />}
        </div>
      </div>

      {result.review.length > 0 && (
        <>
          <h2 className="st-subtitle">Your answers</h2>
          <ol className="st-review">
            {result.review.map((item) => (
              <li key={item.position} className={`st-review-item${item.correct ? " is-correct" : " is-wrong"}`}>
                <p className="st-review-question">{item.question}</p>
                <ul className="st-review-options">
                  {item.options.map((option, i) => {
                    const isAnswer = i === item.correctIndex;
                    const isPicked = i === item.selectedIndex;
                    return (
                      <li
                        key={i}
                        className={`${isAnswer ? "is-answer" : ""}${isPicked && !isAnswer ? " is-picked-wrong" : ""}`}
                      >
                        <span>{option}</span>
                        {isAnswer && <span className="st-tag st-tag-good">Correct answer</span>}
                        {isPicked && !isAnswer && <span className="st-tag st-tag-bad">Your answer</span>}
                        {isPicked && isAnswer && <span className="st-tag st-tag-good">Your answer</span>}
                      </li>
                    );
                  })}
                </ul>
                {item.selectedIndex == null && <p className="st-small st-muted">Not answered</p>}
                {item.explanation && <p className="st-explanation">{item.explanation}</p>}
              </li>
            ))}
          </ol>
        </>
      )}

      <Link className="st-btn st-btn-primary" to={SKILLS_PAGE}>Back to my skills</Link>
    </>
  );
}
