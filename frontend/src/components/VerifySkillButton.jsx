import { Link } from "react-router-dom";
import VerifiedBadge from "./VerifiedBadge";
import "./SkillTest.css";

/**
 * Drop into each row of the My Skills list:
 *   <VerifySkillButton skill={skill} />
 * Expects skill.id, skill.level, skill.verified, skill.verifiedLevel, skill.verificationScore.
 */
export default function VerifySkillButton({ skill }) {
  const fullyVerified = skill.verified && skill.verifiedLevel === skill.level;
  return (
    <span className="st-verify">
      {skill.verified && <VerifiedBadge level={skill.verifiedLevel} score={skill.verificationScore} />}
      {!fullyVerified && (
        <Link className="st-verify-link" to={`/skills/${skill.id}/test`}>
          {skill.verified ? "Verify higher level" : "Verify skill"}
        </Link>
      )}
    </span>
  );
}
