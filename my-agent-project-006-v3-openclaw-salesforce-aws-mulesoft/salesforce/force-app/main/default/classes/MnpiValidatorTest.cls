@isTest
private class MnpiValidatorTest {
    @isTest static void flags_share_count() {
        System.assertEquals('Contains raw share count',
            MnpiValidator.findViolation('Patel owns 1500 shares of NVDA'));
    }
    @isTest static void flags_wire_instructions() {
        System.assertEquals('Contains wire instructions',
            MnpiValidator.findViolation('Please wire $24,000 to account ABC123XYZ'));
    }
    @isTest static void flags_trade_intent() {
        System.assertEquals('Contains trade intent',
            MnpiValidator.findViolation('We plan to sell 150 shares NVDA tomorrow'));
    }
    @isTest static void clean_text_passes() {
        System.assertEquals(null, MnpiValidator.findViolation('NVDA data-center growth continues.'));
        System.assert(MnpiValidator.isClean('neutral text'));
    }
    @isTest static void blank_returns_null() {
        System.assertEquals(null, MnpiValidator.findViolation(''));
        System.assertEquals(null, MnpiValidator.findViolation(null));
    }
}
