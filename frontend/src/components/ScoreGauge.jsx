import { useEffect, useState } from "react";

import { prefersReducedMotion } from "../lib/motion.js";

const SIZE = 120;
const CENTER = SIZE / 2;
const RADIUS = 46;
const STROKE_WIDTH = 10;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const DURATION_MS = 1200;
const TICK_COUNT = 20;
const TICKS = Array.from({ length: TICK_COUNT }, (_, index) => index);

// Ease-out cubic: moves fast at first, then settles gently onto the final value.
function easeOutCubic(progress) {
  return 1 - Math.pow(1 - progress, 3);
}

function tickLine(index) {
  const angle = (index / TICK_COUNT) * 2 * Math.PI - Math.PI / 2;
  const isMajor = index % 5 === 0;
  const innerRadius = isMajor ? 53 : 55;
  const outerRadius = 58;
  return {
    x1: CENTER + innerRadius * Math.cos(angle),
    y1: CENTER + innerRadius * Math.sin(angle),
    x2: CENTER + outerRadius * Math.cos(angle),
    y2: CENTER + outerRadius * Math.sin(angle),
    isMajor,
  };
}

export default function ScoreGauge({ score }) {
  // With reduced motion the gauge starts (and stays) at the final score.
  const [displayed, setDisplayed] = useState(() => (prefersReducedMotion() ? score : 0));

  useEffect(() => {
    if (prefersReducedMotion()) {
      return undefined;
    }

    // WHY requestAnimationFrame rather than a CSS transition: the number in the
    // middle has to count up in step with the arc. CSS can transition the
    // arc's stroke-dashoffset but not a text node's content, so the two would
    // drift apart. rAF drives both from one value, once per display frame, and
    // browsers pause it in background tabs.
    let frameId = null;
    let startTime = null;

    function step(timestamp) {
      if (startTime === null) {
        startTime = timestamp;
      }
      const progress = Math.min((timestamp - startTime) / DURATION_MS, 1);
      setDisplayed(score * easeOutCubic(progress));
      if (progress < 1) {
        frameId = requestAnimationFrame(step);
      }
    }

    frameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameId);
  }, [score]);

  const dashOffset = CIRCUMFERENCE * (1 - displayed / 100);

  return (
    <figure className="gauge" role="img" aria-label={`Match score: ${score} out of 100`}>
      <svg className="gauge__svg" viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
        {TICKS.map((index) => {
          const tick = tickLine(index);
          return (
            <line
              key={index}
              className={tick.isMajor ? "gauge__tick gauge__tick--major" : "gauge__tick"}
              x1={tick.x1}
              y1={tick.y1}
              x2={tick.x2}
              y2={tick.y2}
            />
          );
        })}
        <circle className="gauge__track" cx={CENTER} cy={CENTER} r={RADIUS} fill="none" strokeWidth={STROKE_WIDTH} />
        <circle
          className="gauge__arc"
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          strokeWidth={STROKE_WIDTH}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          transform={`rotate(-90 ${CENTER} ${CENTER})`}
          // A round line cap draws a dot even at 0%, so hide the arc until it has length.
          opacity={displayed < 0.5 ? 0 : 1}
        />
        <text className="gauge__value" x={CENTER} y={CENTER + 6} textAnchor="middle">
          {Math.round(displayed)}
        </text>
        <text className="gauge__unit" x={CENTER} y={CENTER + 22} textAnchor="middle">
          out of 100
        </text>
      </svg>
    </figure>
  );
}
