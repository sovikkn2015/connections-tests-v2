/**
 * HelloAction - The simplest Apex action for Agentforce
 *
 * This class provides a greeting action that the Hello World Agent
 * can call. The @InvocableMethod annotation makes it visible to
 * Agentforce, Flows, and other automation tools.
 */
public with sharing class HelloAction {

    /**
     * Input wrapper - defines what the agent sends to this action
     */
    public class GreetingInput {
        @InvocableVariable(label='User Name' description='The name of the user to greet' required=false)
        public String userName;
    }

    /**
     * Output wrapper - defines what this action returns to the agent
     */
    public class GreetingOutput {
        @InvocableVariable(label='Greeting Message' description='The personalized greeting')
        public String greetingMessage;
    }

    /**
     * The actual action the agent calls.
     * @InvocableMethod makes this callable by Agentforce.
     */
    @InvocableMethod(
        label='Get Greeting'
        description='Returns a personalized greeting message for the user'
    )
    public static List<GreetingOutput> getGreeting(List<GreetingInput> inputs) {
        List<GreetingOutput> outputs = new List<GreetingOutput>();

        for (GreetingInput input : inputs) {
            GreetingOutput output = new GreetingOutput();

            if (String.isNotBlank(input.userName)) {
                output.greetingMessage = 'Hello ' + input.userName + '! '
                    + 'Welcome! I\'m your Hello World agent. '
                    + 'How can I help you today?';
            } else {
                output.greetingMessage = 'Hello there! '
                    + 'Welcome! I\'m your Hello World agent. '
                    + 'What can I do for you?';
            }

            outputs.add(output);
        }

        return outputs;
    }
}
