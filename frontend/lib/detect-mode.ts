const IP_REGEX =
  /\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b/;

export type InputMode = "query" | "investigate";

export interface DetectedIntent {
  mode: InputMode;
  entity?: string;
  entityType?: "ip" | "user" | "host";
}

export function detectIntent(message: string): DetectedIntent {
  const lower = message.toLowerCase();

  const ipMatch = message.match(IP_REGEX);
  if (ipMatch && (lower.includes("investigate") || lower.includes("analyze"))) {
    return { mode: "investigate", entity: ipMatch[0], entityType: "ip" };
  }
  if (ipMatch) {
    return { mode: "investigate", entity: ipMatch[0], entityType: "ip" };
  }

  const investigateUser =
    /investigate\s+user\s+(\S+)/i.exec(message) ||
    /analyze\s+user\s+(\S+)/i.exec(message);
  if (investigateUser) {
    return {
      mode: "investigate",
      entity: investigateUser[1],
      entityType: "user",
    };
  }

  const investigateHost =
    /investigate\s+host\s+(\S+)/i.exec(message) ||
    /investigate\s+hostname\s+(\S+)/i.exec(message);
  if (investigateHost) {
    return {
      mode: "investigate",
      entity: investigateHost[1],
      entityType: "host",
    };
  }

  if (lower.includes("investigate ip")) {
    const ip = message.match(IP_REGEX);
    if (ip) {
      return { mode: "investigate", entity: ip[0], entityType: "ip" };
    }
  }

  if (lower.startsWith("investigate ")) {
    const rest = message.slice("investigate ".length).trim();
    if (IP_REGEX.test(rest)) {
      const ip = rest.match(IP_REGEX);
      return { mode: "investigate", entity: ip![0], entityType: "ip" };
    }
    return { mode: "investigate", entity: rest.split(/\s+/)[0], entityType: "user" };
  }

  return { mode: "query" };
}
