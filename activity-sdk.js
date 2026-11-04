import { DiscordSDK } from "/sdk/@discord/embedded-app-sdk@2.5.0";

const discordSdk = new DiscordSDK("1566288861259108424");

async function connectActivity() {
  const status = document.getElementById("discord-status");

  try {
    await discordSdk.ready();
    if (status) status.textContent = "Connected to Discord";
    console.log("Gaming Network Activity connected");
  } catch (error) {
    if (status) status.textContent = "Open inside Discord to connect";
    console.log("Discord Activity connection:", error);
  }
}

connectActivity();
