import { DiscordSDK } from "/sdk/@discord/embedded-app-sdk@2.5.0";

const discordSdk = new DiscordSDK("1566288861259108424");

async function connectActivity() {
  const status = document.getElementById("discord-status");

  try {
    await discordSdk.ready();

    if (status) {
      status.textContent = "Connected to Discord!";
    }

    const auth = await discordSdk.commands.authorize({
      client_id: "1566288861259108424",
      response_type: "code",
      state: "",
      prompt: "none",
      scope: ["identify"]
    });

    console.log("Discord authorization started", auth);
  } catch (error) {
    if (status) status.textContent = "Discord connection failed";
    console.error(error);
  }
}

connectActivity();
